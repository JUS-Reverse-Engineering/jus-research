#!/usr/bin/env python3
"""sfx_render.py -- play one JUS sound-effect sequence to a WAV, offline.

Why (jus-wmqi.6.12): to hear the hit, guard, dash and move
sounds. They are SSEQ sequences inside SDAT sequence archives (SEQ_BATTLE =
seqarc 0x7A and the fighter archives like SEQ_NA_B_04 = 0x17A), played on a
bank (SBNK) of instruments that point into wave archives (SWAR). This is a
small one-shot sequencer for those files, standard library only.

What it models (the Nitro sound driver as publicly documented; each sound
here is one to six short tracks):
  - SSEQ commands: notes, rests (0x80), program (0x81), open track (0x93),
    jump/call/return (0x94/0x95/0xFD), loop (0xD4/0xFC), random (0xA0),
    variable (0xA1) and if (0xA2) prefixes, variables (0xB0-0xBD), pan,
    volume, master volume, transpose, pitch bend, bend range, mono/poly,
    portamento (0xC9/0xCE/0xCF), modulation (0xCA-0xCD, 0xE0), ADSR
    overrides (0xD0-0xD3), expression (0xD5), tempo (0xE1), sweep pitch
    (0xE3), end (0xFF). Unknown commands stop the track and are reported.
  - Timing: one sound frame = 64 * 2728 / 33513982 s (about 5.21 ms).
    Each frame the tempo counter gains `tempo`; each 240 is one tick.
  - Notes with duration 0 never auto-release (they play until the sample
    ends or the render cap), as the driver only counts down positive lengths.
  - Instruments: PCM (type 1), PSG square (2), noise (3), drum set (16),
    key split (17). SWAV PCM8, PCM16 and IMA-ADPCM, with loops.
  - Envelope: the driver's attack / fall rate conversion and a -92544..0
    amplitude in 1/128 steps of a 0.1 dB unit (inferred unit).
  - Volume: velocity, track volume, expression, master volume and the SSAR
    record volume each as (v/127)^2, like the driver's decibel-square table.
  - Pan: track pan + instrument pan - 64, linear left/right.

What it does not model (so a render is close, not exact): hardware
interpolation (linear here), the exact decibel tables (log formula here),
modulation curve shape (sine here), channel stealing, and what the game
does around the call (the sound wrapper 0x0207342C may set volume or pan).
Random (0xA0) takes the midpoint of its range so renders repeat; the real
game rolls a value each play. PSG pitch: the base (key 69 = 440 Hz) is an
assumption; no target sound in this tracker item uses PSG.

NOT FOR RELEASE: the WAVs are ripped JUS audio. They go under
jus_files/extracted/vfx-sfx/render/wav/ (untracked) and are never committed.

Usage:
    python3 scripts/analysis/sfx_render.py SEQ_BATTLE SE_HIT SE_GUARD 0x2A
    python3 scripts/analysis/sfx_render.py SEQ_NA_B_04 0 --manifest out.json
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))

import sdat_inventory as si  # noqa: E402

SDAT = REPO / "jus_files" / "ripped_jus_files" / "sound" / "JS2_sound.sdat"
OUT = REPO / "jus_files" / "extracted" / "vfx-sfx" / "render" / "wav"
RATE = 32768
FRAME = 64 * 2728 / 33513982
AMP_MIN = -92544
CAP_S = 4.0

ADPCM_INDEX = [-1, -1, -1, -1, 2, 4, 6, 8]
ADPCM_STEP = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45,
              50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230,
              253, 279, 307, 337, 371, 408, 449, 494, 544, 598, 658, 724, 796, 876, 963,
              1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327,
              3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487,
              12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767]
ATTACK_LUT = [0x00, 0x01, 0x05, 0x0E, 0x1A, 0x26, 0x33, 0x3F, 0x49, 0x54, 0x5C, 0x64,
              0x6D, 0x74, 0x7B, 0x7F, 0x84, 0x89, 0x8F]


def _u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


# ------------------------------------------------------------------ envelope math

def attack_rate(a: int) -> int:
    return ATTACK_LUT[0x7F - a] if a >= 0x6D else 0xFF - a


def fall_rate(f: int) -> int:
    if f == 0x7F:
        return 0xFFFF
    if f == 0x7E:
        return 0x3C00
    if f < 0x32:
        return 2 * f + 1
    return 0x1E00 // (0x7E - f)


def db_square(v: int) -> float:
    """(v/127)^2 as 0.1 dB units, floored at -72.3 dB (log formula, not the table)."""
    if v <= 0:
        return -723.0
    return max(-723.0, 400.0 * math.log10(min(v, 127) / 127))


def gain_of(units: float) -> float:
    return 10 ** (units / 200.0)


# ------------------------------------------------------------------ files

class Sdat:
    def __init__(self, path: Path = SDAT):
        self.b = path.read_bytes()
        self.d = si.parse_sdat(self.b)

    def fat(self, fid: int) -> bytes:
        off, size = self.d["fat"][fid]
        return self.b[off:off + size]

    def seqarc_index(self, name_or_index: str) -> int:
        names = self.d["symb"]["seqarc"]
        if name_or_index in names:
            return names.index(name_or_index)
        return int(name_or_index, 0)


def parse_sbnk(blob: bytes) -> list:
    """Instrument list: None or (type, payload)."""
    if blob[:4] != b"SBNK":
        raise ValueError("not an SBNK")
    n = struct.unpack_from("<I", blob, 0x38)[0]
    out = []
    for i in range(n):
        kind, off = blob[0x3C + 4 * i], _u16(blob, 0x3C + 4 * i + 1)
        out.append(None if kind == 0 else (kind, _instrument(blob, kind, off)))
    return out


def _notedef(blob, o, kind):
    swav, swar, key, a, d, s, r, pan = struct.unpack_from("<HHBBBBBB", blob, o)
    return {"type": kind, "swav": swav, "swar": swar, "key": key,
            "adsr": (a, d, s, r), "pan": pan}


def _instrument(blob, kind, off):
    if kind in (1, 2, 3, 4, 5):
        return [(0, 127, _notedef(blob, off, kind))]
    if kind == 16:
        lo, hi = blob[off], blob[off + 1]
        return [(k, k, _notedef(blob, off + 2 + 12 * (k - lo) + 2, _u16(blob, off + 2 + 12 * (k - lo))))
                for k in range(lo, hi + 1)]
    if kind == 17:
        tops = [t for t in blob[off:off + 8] if t]
        out, lo = [], 0
        for j, top in enumerate(tops):
            o = off + 8 + 12 * j
            out.append((lo, top, _notedef(blob, o + 2, _u16(blob, o))))
            lo = top + 1
        return out
    raise ValueError(f"instrument type {kind}")


def region(bank: list, program: int, key: int):
    if program >= len(bank) or bank[program] is None:
        return None
    for lo, hi, nd in bank[program][1]:
        if lo <= key <= hi:
            return nd
    return None


def parse_swar(blob: bytes) -> list[bytes]:
    if blob[:4] != b"SWAR":
        raise ValueError("not an SWAR")
    n = struct.unpack_from("<I", blob, 0x38)[0]
    offs = [struct.unpack_from("<I", blob, 0x3C + 4 * i)[0] for i in range(n)] + [len(blob)]
    return [blob[offs[i]:offs[i + 1]] for i in range(n)]


def decode_swav(sw: bytes) -> dict:
    """{kind, rate, loop (sample index or None), samples [-1, 1]}."""
    kind, loops, rate, _timer, loop_w, len_w = struct.unpack_from("<BBHHHI", sw, 0)
    data = sw[0xC:0xC + 4 * (loop_w + len_w)]
    if kind == 0:
        s = [((x ^ 0x80) - 128) / 128 for x in data]
        lp = loop_w * 4
    elif kind == 1:
        s = [v / 32768 for v in struct.unpack_from(f"<{len(data) // 2}h", data)]
        lp = loop_w * 2
    elif kind == 2:
        pred, idx = struct.unpack_from("<hB", data, 0)
        idx = min(idx, 88)
        s = []
        for byte in data[4:]:
            for nib in (byte & 15, byte >> 4):
                step = ADPCM_STEP[idx]
                diff = step >> 3
                if nib & 1:
                    diff += step >> 2
                if nib & 2:
                    diff += step >> 1
                if nib & 4:
                    diff += step
                pred = max(-32767, pred - diff) if nib & 8 else min(32767, pred + diff)
                idx = min(88, max(0, idx + ADPCM_INDEX[nib & 7]))
                s.append(pred / 32768)
        lp = max(0, (loop_w * 4 - 4) * 2)
    else:
        raise ValueError(f"SWAV type {kind}")
    return {"kind": kind, "rate": rate, "loop": lp if loops else None, "samples": s}


# ------------------------------------------------------------------ sequencer

class Voice:
    def __init__(self, nd, wave_, key, vel, length, track, sweep, sweep_len):
        self.nd, self.wave, self.key, self.length = nd, wave_, key, length
        a, d, s, r = nd["adsr"]
        ov = track.adsr
        a, d, s, r = [o if o != 0xFF else v for o, v in zip(ov, (a, d, s, r))]
        self.att, self.dec, self.sus, self.rel = attack_rate(a), fall_rate(d), db_square(s) * 128, fall_rate(r)
        self.amp = AMP_MIN if self.att else 0
        self.phase = "attack" if self.att else "decay"
        self.vel_db = db_square(vel)
        self.track = track
        self.pos = 0.0
        self.sweep, self.sweep_len, self.sweep_t = sweep, sweep_len, 0
        self.mod_t, self.mod_delay = 0, track.mod_delay
        self.noise = 0x7FFF
        self.done = False

    def release(self):
        if self.phase != "release":
            self.phase = "release"

    def frame(self):
        if self.phase == "attack":
            self.amp = -((self.att * -self.amp) >> 8) if self.amp < 0 else 0
            if self.amp >= -128:
                self.amp, self.phase = 0, "decay"
        elif self.phase == "decay":
            self.amp -= self.dec
            if self.amp <= self.sus:
                self.amp, self.phase = self.sus, "sustain"
        elif self.phase == "release":
            self.amp -= self.rel
            if self.amp <= AMP_MIN:
                self.done = True
        if self.mod_delay > 0:
            self.mod_delay -= 1
        else:
            self.mod_t += self.track.mod_speed << 6

    def pitch_semitones(self) -> float:
        t = self.track
        p = self.key - self.nd["key"] + t.transpose + t.bend * t.bend_range / 128
        if self.sweep and self.sweep_len > 0 and self.sweep_t < self.sweep_len:
            p += self.sweep * (self.sweep_len - self.sweep_t) / self.sweep_len / 64
        if t.mod_type == 0 and t.mod_depth and self.mod_delay <= 0:
            p += self.lfo() * t.mod_depth * t.mod_range / 256 / 64
        return p

    def lfo(self) -> float:
        return 127 * math.sin(2 * math.pi * ((self.mod_t >> 8) % 128) / 128)


class Track:
    def __init__(self, player, pc):
        self.p, self.pc = player, pc
        self.wait = 0
        self.ended = False
        self.program = 0
        self.volume, self.expression, self.pan, self.transpose = 127, 127, 64, 0
        self.bend, self.bend_range = 0, 2
        self.note_wait = True
        self.porta_on, self.porta_key, self.porta_time = False, 60, 0
        self.sweep_pitch = 0
        self.mod_depth, self.mod_speed, self.mod_type, self.mod_range, self.mod_delay = 0, 16, 0, 1, 0
        self.adsr = [0xFF] * 4
        self.stack = []
        self.cond = True

    # byte readers
    def u8(self):
        v = self.p.data[self.pc]
        self.pc += 1
        return v

    def u16(self):
        v = _u16(self.p.data, self.pc)
        self.pc += 2
        return v

    def u24(self):
        v = self.p.data[self.pc] | self.p.data[self.pc + 1] << 8 | self.p.data[self.pc + 2] << 16
        self.pc += 3
        return v

    def vl(self):
        v = 0
        while True:
            b = self.u8()
            v = (v << 7) | (b & 0x7F)
            if not b & 0x80:
                return v

    def arg(self, kind, mode):
        if mode == "random":
            lo, hi = struct.unpack_from("<hh", self.p.data, self.pc)
            self.pc += 4
            return (lo + hi) // 2
        if mode == "var":
            return self.p.vars[self.u8()]
        return {"u8": self.u8, "s8": lambda: (self.u8() ^ 0x80) - 0x80, "u16": self.u16,
                "s16": lambda: (self.u16() ^ 0x8000) - 0x8000, "vl": self.vl}[kind]()

    def tick(self):
        if self.ended:
            return
        if self.wait > 0:
            self.wait -= 1
        guard = 0
        while self.wait == 0 and not self.ended:
            guard += 1
            if guard > 10000:
                self.p.problems.append("runaway track")
                self.ended = True
                return
            self.step()

    def step(self):
        c = self.u8()
        mode = None
        if c == 0xA0:
            mode, c = "random", self.u8()
        elif c == 0xA1:
            mode, c = "var", self.u8()
        elif c == 0xA2:
            run = self.cond
            c = self.u8()
            if not run:
                self._skip(c)
                return
        self.p.commands.add(c)
        if c < 0x80:
            vel = self.u8()
            length = self.arg("vl", mode)
            self.p.note(self, c + 0, vel, length)
            if self.note_wait:
                self.wait = length
        elif c == 0x80:
            self.wait = self.arg("vl", mode)
        elif c == 0x81:
            self.program = self.arg("vl", mode)
        elif c == 0x93:
            t, off = self.u8(), self.u24()
            self.p.open_track(t, off)
        elif c == 0x94:
            self.pc = self.p.base + self.u24()
        elif c == 0x95:
            to = self.u24()
            self.stack.append(("call", self.pc))
            self.pc = self.p.base + to
        elif c == 0xFD:
            while self.stack and self.stack[-1][0] != "call":
                self.stack.pop()
            if self.stack:
                self.pc = self.stack.pop()[1]
        elif c == 0xD4:
            count = self.arg("u8", mode)
            self.stack.append(["loop", self.pc, count])
        elif c == 0xFC:
            if self.stack and self.stack[-1][0] == "loop":
                top = self.stack[-1]
                if top[2] == 0:
                    self.pc = top[1]      # 0 = loop forever
                elif top[2] > 1:
                    top[2] -= 1
                    self.pc = top[1]
                else:
                    self.stack.pop()
        elif 0xB0 <= c <= 0xBD:
            v, val = self.u8(), self.arg("s16", mode)
            self._var(c, v, val)
        elif c == 0xFE:
            self.u16()
        elif c == 0xFF:
            self.ended = True
        elif c in U8_SETTERS:
            setattr(self, U8_SETTERS[c], self.arg("u8", mode))
        elif c == 0xC3:
            self.transpose = self.arg("s8", mode)
        elif c == 0xC4:
            self.bend = self.arg("s8", mode)
        elif c == 0xC7:
            self.note_wait = bool(self.arg("u8", mode))
        elif c == 0xCE:
            self.porta_on = bool(self.arg("u8", mode))
        elif c in (0xD0, 0xD1, 0xD2, 0xD3):
            self.adsr[c - 0xD0] = self.arg("u8", mode)
        elif c == 0xC2:
            self.p.master = self.arg("u8", mode)
        elif c == 0xE0:
            self.mod_delay = self.arg("s16", mode)
        elif c == 0xE1:
            self.p.tempo = self.arg("u16", mode)
        elif c == 0xE3:
            self.sweep_pitch = self.arg("s16", mode)
        elif c in (0xC6, 0xC8, 0xD6):
            self.arg("u8", mode)
            if c == 0xC8:
                self.p.problems.append("tie (0xC8) not modelled")
        else:
            self.p.problems.append(f"unknown command 0x{c:02x}")
            self.ended = True

    def _skip(self, c):
        """Skip one command's arguments (for a false 0xA2 if)."""
        if c < 0x80:
            self.u8()
            self.vl()
        elif c in (0x80, 0x81):
            self.vl()
        elif c == 0x93:
            self.pc += 4
        elif c in (0x94, 0x95):
            self.pc += 3
        elif 0xB0 <= c <= 0xBD:
            self.pc += 3
        elif c in (0xE0, 0xE1, 0xE3, 0xFE):
            self.pc += 2
        elif 0xC0 <= c <= 0xDF:
            self.pc += 1

    def _var(self, c, v, val):
        vs = self.p.vars
        if c == 0xB0:
            vs[v] = val
        elif c == 0xB1:
            vs[v] += val
        elif c == 0xB2:
            vs[v] -= val
        elif c == 0xB3:
            vs[v] *= val
        elif c == 0xB4:
            vs[v] = int(vs[v] / val) if val else vs[v]
        elif c == 0xB5:
            vs[v] = vs[v] << val if val >= 0 else vs[v] >> -val
        elif c == 0xB6:
            vs[v] = abs(val) // 2          # random: midpoint of 0..val
        else:
            self.cond = [vs[v] == val, vs[v] >= val, vs[v] > val,
                         vs[v] <= val, vs[v] < val, vs[v] != val][c - 0xB8]


U8_SETTERS = {0xC0: "pan", 0xC1: "volume", 0xC5: "bend_range", 0xC9: "porta_key",
              0xCA: "mod_depth", 0xCB: "mod_speed", 0xCC: "mod_type", 0xCD: "mod_range",
              0xCF: "porta_time", 0xD5: "expression"}


class Player:
    def __init__(self, data, base, start, bank, waves, seq_volume):
        self.data, self.base = data, base
        self.bank, self.waves = bank, waves
        self.seq_volume = seq_volume
        self.tempo, self.master = 120, 127
        self.vars = [0] * 32
        self.tracks = [Track(self, base + start)]
        self.voices = []
        self.problems, self.commands = [], set()
        self.notes = []

    def open_track(self, n, off):
        self.tracks.append(Track(self, self.base + off))

    def note(self, track, key, vel, length):
        key = min(127, max(0, key + track.transpose))
        nd = region(self.bank, track.program, key)
        if nd is None:
            self.problems.append(f"no instrument for program {track.program} key {key}")
            return
        sweep = track.sweep_pitch
        if track.porta_on:
            sweep += (track.porta_key - key) << 6
        track.porta_key = key
        if track.porta_time == 0:
            sweep_len = length
        else:
            sweep_len = (track.porta_time * track.porta_time * abs(sweep)) >> 11
        wave_ = None
        if nd["type"] == 1:
            wave_ = self.waves(nd["swar"], nd["swav"])
            if wave_ is None:
                self.problems.append(f"missing wave {nd['swar']}/{nd['swav']}")
                return
        self.notes.append({"key": key, "velocity": vel, "length": length, "program": track.program,
                           "type": nd["type"], "swar": nd["swar"], "swav": nd["swav"]})
        v = Voice(nd, wave_, key, vel, length, track, sweep, sweep_len)
        self.voices.append(v)

    def tick_voices(self):
        for v in self.voices:
            if v.length > 0:
                v.length -= 1
                if v.length == 0:
                    v.release()
            if v.sweep_t < v.sweep_len:
                v.sweep_t += 1

    def render(self, cap_s: float = CAP_S):
        out_l, out_r = [], []
        counter, frames, spf, acc = 0, 0, RATE * FRAME, 0.0
        while frames * FRAME < cap_s:
            for v in self.voices:
                v.frame()
            counter += self.tempo
            while counter >= 240:
                counter -= 240
                for t in list(self.tracks):
                    t.tick()
                self.tick_voices()
            acc += spf
            n = int(acc)
            acc -= n
            self._mix(n, out_l, out_r)
            self.voices = [v for v in self.voices if not v.done]
            frames += 1
            if all(t.ended for t in self.tracks) and not self.voices:
                break
        return out_l, out_r

    def _mix(self, n, out_l, out_r):
        buf_l, buf_r = [0.0] * n, [0.0] * n
        for v in self.voices:
            t = v.track
            units = (v.amp / 128 + v.vel_db + db_square(t.volume) + db_square(t.expression)
                     + db_square(self.master) + db_square(self.seq_volume))
            if t.mod_type == 1 and t.mod_depth and v.mod_delay <= 0:
                units += v.lfo() * t.mod_depth * t.mod_range / 256 * 0.6
            g = gain_of(units)
            pan = t.pan + v.nd["pan"] - 64
            if t.mod_type == 2 and t.mod_depth and v.mod_delay <= 0:
                pan += v.lfo() * t.mod_depth * t.mod_range / 256 / 64 * 64
            pan = min(127, max(0, pan))
            gl, gr = g * (128 - pan) / 128, g * pan / 128
            f = self._freq(v)
            for i in range(n):
                s = self._sample(v, f)
                if s is None:
                    v.done = True
                    break
                buf_l[i] += s * gl
                buf_r[i] += s * gr
        out_l.extend(buf_l)
        out_r.extend(buf_r)

    def _freq(self, v):
        semis = v.pitch_semitones()
        if v.nd["type"] == 1:
            return v.wave["rate"] * 2 ** (semis / 12) / RATE
        return 440 * 2 ** ((v.key - 69 + semis - (v.key - v.nd["key"])) / 12) / RATE

    def _sample(self, v, step):
        kind = v.nd["type"]
        if kind == 1:
            s = v.wave["samples"]
            i = int(v.pos)
            if i + 1 >= len(s):
                if v.wave["loop"] is None:
                    return None
                v.pos -= len(s) - v.wave["loop"]
                i = int(v.pos)
            fr = v.pos - i
            a = s[i]
            b = s[i + 1] if i + 1 < len(s) else (s[v.wave["loop"]] if v.wave["loop"] is not None else a)
            v.pos += step
            return a + (b - a) * fr
        if kind == 2:
            duty = (v.nd["swav"] % 8 + 1) / 8
            v.pos = (v.pos + step) % 1.0
            return 0.5 if v.pos < duty else -0.5
        if kind == 3:
            v.pos += step * 8
            while v.pos >= 1:
                v.pos -= 1
                bit = v.noise & 1
                v.noise >>= 1
                if bit:
                    v.noise ^= 0x6000
            return 0.5 if v.noise & 1 else -0.5
        return None


# ------------------------------------------------------------------ top level

def load(sdat: Sdat, seqarc: int, seq: int):
    """(player, record) for one sequence of one sequence archive."""
    ssar = sdat.fat(si.seqarc_file_id(sdat.b, sdat.d, seqarc))
    rec = si.parse_ssar(ssar)
    r = rec["records"][seq]
    if r["offset"] is None:
        raise ValueError(f"seqarc {seqarc} sequence {seq} is empty")
    bi = si.bank_info(sdat.b, sdat.d, r["bank"])
    bank = parse_sbnk(sdat.fat(bi["file_id"]))
    cache: dict = {}

    def waves(slot, idx):
        wa = bi["wavarcs"][slot] if slot < 4 else 0xFFFF
        if wa == 0xFFFF:
            return None
        key = (wa, idx)
        if key not in cache:
            fid = si.info_file_id(sdat.b, sdat.d["blocks"][1][0], sdat.d["info"]["wavarc"][wa])
            lst = parse_swar(sdat.fat(fid))
            cache[key] = decode_swav(lst[idx]) if idx < len(lst) else None
        return cache[key]

    p = Player(ssar, rec["data_offset"], r["offset"], bank, waves, r["volume"])
    return p, r, bi


def stats(left, right) -> dict:
    peak = max((max(abs(x) for x in ch) for ch in (left, right) if ch), default=0.0)
    thr = 10 ** (-60 / 20)
    last = 0
    for i in range(len(left) - 1, -1, -1):
        if abs(left[i]) > thr or abs(right[i]) > thr:
            last = i + 1
            break
    first = next((i for i in range(len(left)) if abs(left[i]) > thr or abs(right[i]) > thr), None)
    rms = math.sqrt(sum(x * x for x in left + right) / max(1, 2 * len(left)))
    return {"samples": len(left), "seconds": round(len(left) / RATE, 3),
            "audible_seconds": round((last - (first or 0)) / RATE, 3) if first is not None else 0.0,
            "starts_at_s": round(first / RATE, 3) if first is not None else None,
            "peak_dbfs": round(20 * math.log10(peak), 1) if peak > 0 else None,
            "rms_dbfs": round(20 * math.log10(rms), 1) if rms > 0 else None,
            "silent": peak < thr}


def write_wav(path: Path, left, right, norm: float = 1.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = bytearray()
    for a, b in zip(left, right):
        frames += struct.pack("<hh", max(-32768, min(32767, int(a * norm * 32767))),
                              max(-32768, min(32767, int(b * norm * 32767))))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))


def render_one(sdat: Sdat, seqarc: int, seq: int, out_dir: Path | None, cap_s: float = CAP_S) -> dict:
    names = sdat.d["symb"]["seqarc_seqs"][seqarc]
    name = names[seq] if seq < len(names) and names[seq] else f"seq{seq}"
    p, r, bi = load(sdat, seqarc, seq)
    left, right = p.render(cap_s)
    st = stats(left, right)
    row = {"seqarc": seqarc, "seqarc_name": sdat.d["symb"]["seqarc"][seqarc], "index": seq,
           "name": name, "bank": r["bank"], "bank_name": sdat.d["symb"]["bank"][r["bank"]],
           "ssar_volume": r["volume"], "notes": p.notes, "problems": sorted(set(p.problems)),
           "hit_cap": st["seconds"] >= cap_s - 0.01, **st}
    if out_dir is not None:
        f = out_dir / f"{sdat.d['symb']['seqarc'][seqarc]}_{seq:02x}_{name}.wav"
        write_wav(f, left, right)
        row["wav"] = str(f.relative_to(REPO)) if f.is_relative_to(REPO) else str(f)
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("seqarc", help="SEQARC name (SEQ_BATTLE) or index")
    ap.add_argument("seqs", nargs="+", help="sequence names (SE_HIT) or indexes")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--cap", type=float, default=CAP_S, help="render cap in seconds")
    ap.add_argument("--manifest", type=Path)
    a = ap.parse_args(argv)
    sdat = Sdat()
    sa = sdat.seqarc_index(a.seqarc)
    names = sdat.d["symb"]["seqarc_seqs"][sa]
    rows = []
    for s in a.seqs:
        idx = names.index(s) if s in names else int(s, 0)
        row = render_one(sdat, sa, idx, a.out, a.cap)
        rows.append(row)
        print(f"{row['name']:<22} peak {row['peak_dbfs']} dBFS  audible {row['audible_seconds']} s"
              f"  notes {len(row['notes'])}  problems {row['problems']}")
    if a.manifest:
        a.manifest.write_text(json.dumps(rows, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
