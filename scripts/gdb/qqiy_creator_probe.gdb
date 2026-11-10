# Creator resolution probe for jus-qqiy.
#
# Extends scripts/gdb/flp3_creation_probe.gdb (jus-flp3, 2026-09-11). flp3
# found that r1 at 0x0207CA70 (creator) never equals either fighter-object
# pointer (0x021DEB3C/0x021DEB40) and changes between creations inside a
# single run -- see docs/research/feel-captures/projectile-conflict-2026-09-11/SUMMARY.md
# "Creator resolution: r1 never matched either fighter-object pointer". This
# probe widens the search: instead of only checking r1 itself against
# p1/p2, it dumps r1's own first 0x40 bytes and the record's first 0x34
# bytes and marks every word that IS p1/p2 or points INTO the fighter
# object's first 0x1000 bytes (i.e. r1/record fields that are themselves
# pointers back to the fighter, not the creator handle itself). It also
# dumps node 0's first 0x24 bytes the same way, at every FLAG_0x9 hit (not
# gated to "first per record" in the script -- GDB convenience variables
# have no practical per-address dedup here; RESULTS.md analysis takes the
# first log line per distinct rec=0x... value, which is equivalent to
# "first FLAG_0x9 hit per record" without adding untested state-tracking
# logic to this script).
#
# r1 is captured at the 0x0207C988 entry breakpoint into $qqiy_owner, per
# jus-qqiy step 1, rather than re-read as plain $r1 at 0x0207CA70 -- the
# call at 0x0207C988 is the manager-level entry (mgr=r0, owner=r1) and
# 0x0207CA70 is reached via a call chain flp3_creation_probe.gdb already
# treats as preserving r1 across (it read $r1 directly there); this probe
# does not assume that and instead threads the value explicitly.
#
# Rules carried over from flp3_creation_probe.gdb: no gameplay naming of
# node +0x18 bit 0, entry +0x08 bit 5, or record+0x38 0x800. This probe
# additionally must not name any newly-found field's gameplay meaning --
# only report offset + p1/p2 marker.
#
# mark legend (fixed 2026-09-11, refuter item 6): 0 = no match, 1 = equals
# p1 exactly, 2 = equals p2 exactly, 3 = in [p1, p1+0x1000) but not equal to
# p1, 4 = in [p2, p2+0x1000) but not equal to p2. The original version set
# mark=1/2 on an exact hit and then unconditionally re-tested the same
# value against the range checks, which overwrite an exact match (p1/p2
# themselves satisfy their own range test) -- mark 1/2 could never survive
# to the printf. Every block below now tests exact-equals first and only
# falls through to the range test in an else branch, so 1/2 and 3/4 are
# mutually exclusive and 1/2 can actually appear in the log.
#
# CREATE_REC now also prints a SELFCHECK line (refuter item 7): whether
# record+0x30, read at installation, already equals the r1 captured at the
# 0x0207C988 entry. RESULTS.md/SUMMARY.md read record+0x30 downstream as
# "the creator handle" on that assumption; this line confirms it instead of
# leaving it inferred.
#
# +0x1000 window basis: fighter-object fields are documented out to +0x1A8
# (docs/confirmed-facts/physics.md:736); no known field lives anywhere near
# +0x1000, so a match there is not a plausible legitimate fighter field --
# it would need explaining, not assuming. Ad hoc rescans at +0x4000/+0x10000
# past each fighter pointer, and of the whole 0x02228000-0x02250000 region,
# turned up zero hits in either run this probe was used for.

set pagination off
set confirm off
set logging file qqiy_creator.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $qqiy_seq = 0
set $qqiy_p1 = 0x021DEB3C
set $qqiy_p2 = 0x021DEB40
set $qqiy_owner = 0

# Manager-level entry: capture r1 (owner arg) before any call chain can
# clobber it by the time we reach the record-install breakpoint.
break *0x0207C988
commands
  silent
  set $qqiy_owner = $r1
  printf "ENTRY mgr=0x%x owner=0x%x arg34=0x%x arg38=0x%x arg3c=0x%x lr=0x%x\n", $r0, $r1, $r2, $r3, *(unsigned int*)($sp), $lr
  continue
end

break *0x0207CA70
commands
  silent
  set $qqiy_seq = $qqiy_seq + 1
  set $rec = $r4
  set $r1cap = $qqiy_owner
  set $p1ptr = *(unsigned int*)($qqiy_p1)
  set $p2ptr = *(unsigned int*)($qqiy_p2)

  printf "CREATE_REC seq=%d record=0x%x r1=0x%x p1=0x%x p2=0x%x f34=0x%x f38=0x%x f3c=0x%x\n", $qqiy_seq, $rec, $r1cap, $p1ptr, $p2ptr, *(unsigned int*)($rec+0x34), *(unsigned int*)($rec+0x38), *(unsigned int*)($rec+0x3c)

  # Self-check (jus-qqiy refuter item 7): record+0x30 is read elsewhere in
  # this probe/RESULTS as "the creator handle", on the assumption that it
  # equals the r1 captured at the 0x0207C988 entry. Confirm that assumption
  # holds at the point of installation itself, for every created record,
  # instead of only inferring it from matching values downstream.
  set $qqiy_selfcheck = (*(unsigned int*)($rec+0x30) == $r1cap)
  printf "  SELFCHECK seq=%d rec30=0x%x r1cap=0x%x match=%d\n", $qqiy_seq, *(unsigned int*)($rec+0x30), $r1cap, $qqiy_selfcheck

  # r1[0x00..0x3C], 16 words
  set $qqiy_i = 0
  while $qqiy_i < 16
    set $qqiy_off = $qqiy_i * 4
    set $qqiy_v = *(unsigned int*)($r1cap + $qqiy_off)
    set $qqiy_mark = 0
    if $qqiy_v == $p1ptr
      set $qqiy_mark = 1
    else
      if $qqiy_v == $p2ptr
        set $qqiy_mark = 2
      else
        if $qqiy_v >= $p1ptr && $qqiy_v < ($p1ptr + 0x1000)
          set $qqiy_mark = 3
        else
          if $qqiy_v >= $p2ptr && $qqiy_v < ($p2ptr + 0x1000)
            set $qqiy_mark = 4
          end
        end
      end
    end
    printf "  R1WORD seq=%d off=0x%02x val=0x%x mark=%d\n", $qqiy_seq, $qqiy_off, $qqiy_v, $qqiy_mark
    set $qqiy_i = $qqiy_i + 1
  end

  # record[0x00..0x30], 13 words
  set $qqiy_i = 0
  while $qqiy_i < 13
    set $qqiy_off = $qqiy_i * 4
    set $qqiy_v = *(unsigned int*)($rec + $qqiy_off)
    set $qqiy_mark = 0
    if $qqiy_v == $p1ptr
      set $qqiy_mark = 1
    else
      if $qqiy_v == $p2ptr
        set $qqiy_mark = 2
      else
        if $qqiy_v >= $p1ptr && $qqiy_v < ($p1ptr + 0x1000)
          set $qqiy_mark = 3
        else
          if $qqiy_v >= $p2ptr && $qqiy_v < ($p2ptr + 0x1000)
            set $qqiy_mark = 4
          end
        end
      end
    end
    printf "  RECWORD seq=%d off=0x%02x val=0x%x mark=%d\n", $qqiy_seq, $qqiy_off, $qqiy_v, $qqiy_mark
    set $qqiy_i = $qqiy_i + 1
  end

  # Node walk, unchanged from flp3_creation_probe.gdb (cap 16, self-loop
  # guard), kept so this probe's logs stay directly comparable.
  set $qqiy_head = *(unsigned int*)($rec+0x08)
  set $qqiy_node = $qqiy_head
  set $qqiy_j = 0
  while $qqiy_node != 0 && $qqiy_j < 16
    set $qqiy_n18 = *(unsigned int*)($qqiy_node+0x18)
    set $qqiy_entry = *(unsigned int*)($qqiy_node+0x10)
    printf "  NODE seq=%d j=%d addr=0x%x n18=0x%x entry=0x%x\n", $qqiy_seq, $qqiy_j, $qqiy_node, $qqiy_n18, $qqiy_entry
    set $qqiy_next = *(unsigned int*)($qqiy_node+0x00)
    if $qqiy_next == $qqiy_node || $qqiy_next == $qqiy_head
      set $qqiy_node = 0
    else
      set $qqiy_node = $qqiy_next
    end
    set $qqiy_j = $qqiy_j + 1
  end

  continue
end

break *0x0207FAD4
commands
  silent
  set $p1ptr = *(unsigned int*)($qqiy_p1)
  set $p2ptr = *(unsigned int*)($qqiy_p2)
  printf "FLAG_0x9 rec=0x%x f34=0x%x f3c=0x%x r0=0x%x lr=0x%x\n", $r4, *(unsigned int*)($r4+0x34), *(unsigned int*)($r4+0x3c), $r0, $lr

  # record[0x00..0x30], 13 words, p1/p2 marked -- pre-existing records
  # (e.g. rec49/50/51/70) never pass through the CREATE_REC breakpoint in
  # a run where they already existed at load, so this is the only place
  # their record body gets dumped (jus-qqiy step 3(b) requirement).
  set $qqiy_i = 0
  while $qqiy_i < 13
    set $qqiy_off = $qqiy_i * 4
    set $qqiy_v = *(unsigned int*)($r4 + $qqiy_off)
    set $qqiy_mark = 0
    if $qqiy_v == $p1ptr
      set $qqiy_mark = 1
    else
      if $qqiy_v == $p2ptr
        set $qqiy_mark = 2
      else
        if $qqiy_v >= $p1ptr && $qqiy_v < ($p1ptr + 0x1000)
          set $qqiy_mark = 3
        else
          if $qqiy_v >= $p2ptr && $qqiy_v < ($p2ptr + 0x1000)
            set $qqiy_mark = 4
          end
        end
      end
    end
    printf "  RECWORD_AT_0x9 rec=0x%x off=0x%02x val=0x%x mark=%d\n", $r4, $qqiy_off, $qqiy_v, $qqiy_mark
    set $qqiy_i = $qqiy_i + 1
  end

  set $qqiy_head = *(unsigned int*)($r4+0x08)
  if $qqiy_head != 0
    # node 0 only: [0x00..0x20], 9 words, p1/p2 marked
    set $qqiy_i = 0
    while $qqiy_i < 9
      set $qqiy_off = $qqiy_i * 4
      set $qqiy_v = *(unsigned int*)($qqiy_head + $qqiy_off)
      set $qqiy_mark = 0
      if $qqiy_v == $p1ptr
        set $qqiy_mark = 1
      else
        if $qqiy_v == $p2ptr
          set $qqiy_mark = 2
        else
          if $qqiy_v >= $p1ptr && $qqiy_v < ($p1ptr + 0x1000)
            set $qqiy_mark = 3
          else
            if $qqiy_v >= $p2ptr && $qqiy_v < ($p2ptr + 0x1000)
              set $qqiy_mark = 4
            end
          end
        end
      end
      printf "  NODE0WORD rec=0x%x off=0x%02x val=0x%x mark=%d\n", $r4, $qqiy_off, $qqiy_v, $qqiy_mark
      set $qqiy_i = $qqiy_i + 1
    end
  end

  # Node walk, unchanged from flp3_creation_probe.gdb.
  set $qqiy_node = $qqiy_head
  set $qqiy_j = 0
  while $qqiy_node != 0 && $qqiy_j < 16
    set $qqiy_n18 = *(unsigned int*)($qqiy_node+0x18)
    set $qqiy_entry = *(unsigned int*)($qqiy_node+0x10)
    printf "  NODE_AT_0x9 rec=0x%x j=%d addr=0x%x n18=0x%x entry=0x%x\n", $r4, $qqiy_j, $qqiy_node, $qqiy_n18, $qqiy_entry
    set $qqiy_next = *(unsigned int*)($qqiy_node+0x00)
    if $qqiy_next == $qqiy_node || $qqiy_next == $qqiy_head
      set $qqiy_node = 0
    else
      set $qqiy_node = $qqiy_next
    end
    set $qqiy_j = $qqiy_j + 1
  end
  continue
end

break *0x0207FB0C
commands
  silent
  printf "FLAG_0x209 rec=0x%x f34=0x%x f3c=0x%x r0=0x%x lr=0x%x\n", $r4, *(unsigned int*)($r4+0x34), *(unsigned int*)($r4+0x3c), $r0, $lr
  continue
end

printf "PROBE_ARMED\n"
continue
