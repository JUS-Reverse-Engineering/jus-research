# Action Replay codes — raw text (owner-supplied 2026-09-02)

The owner pasted this from a gbatemp.net thread (Game Code AJUJ, Game ID
65e1d889). It is the primary source behind `Cheat-Code-Analysis.md` and the
"AR character struct" table in the [archived struct map](archive/Character-State-Struct-2026-02.md). Kept verbatim so
later readers can check the decoded tables against it. Owner's note: it is
unclear how many of these work as intended. The wifi-tagged ones are the ones
the owner recalls working over wifi.

## What the raw text shows that the decoded tables did not

The decoded tables treated `+0x78` (ground/air), `+0x88`/`+0xA0` (status),
`+0xD9`/`+0xDA` (jumps / air actions) and `+0x102` (defense) as offsets on one
struct. The raw codes use **two different bases**:

| code | base | indirection | offset |
|---|---|---|---|
| Have Positive Status / Immune to negative status / Infinite jumps / Defense never wears (local) | `b2181b28` = deref `[0x02181B28]` | one | `+0x88`, `+0xA0`, `+0xD9`, `+0xDA`, `+0x102` |
| same, wifi variants | `b21e2a7c..88` = deref `[0x021E2A7C + 4·p]` | one | `+0xA0`, `+0xD9`, `+0xDA` |
| Always on Ground / Always in Air | `b23d2a74` then `b0000010` = deref `[[0x023D2A74] + 0x10]` | **two** | `+0x78` = `0x22` / `0x00` |

So the `+0x78` row was never on the same object as `+0x102`. This is the
reachability basis for the `jus-fighter-object-ar-plus-0x78-p7um` mismatch;
the falsification test is a live read of `[[0x023D2A74]+0x10]+0x78` in a
grounded `pc-*` state (expect `0x22`) alongside `[0x02181B28]` (expect a
pointer into the ov6 fighter-object region, e.g. `0x02228E80` for P1).

Other cross-checks against known RAM:

- `221df1d5 00000040` (Infinite Health) writes the byte at `0x021DF1D5`, and
  the next three at `+0x50` steps (`…225`, `…275`, `…2C5`). That is the deck
  HP record (`rec = 0x021DF1D4 + 0x50·i`, `rec+0x00` HP as s16): the code pins
  the high byte at 0x40.
- `221DEA71 00000099` (Unlimited Time) and `121dea70` (end game / time 99)
  put the match timer at `0x021DEA70`. Wifi variant is `0x021E29B0`.
- `221DF731 00000009` / `221DF8B1` (Unlimited Special, X) are SP-related
  bytes at `0x021DF731` and `0x021DF8B1` (`+0x180` apart).
- `020afeb4` (deck select) is the address `jus-fms` wants a write-watch on
  (`0x020AFEB8` is 4 bytes later).

## Raw text

```
Ones that work for wifi:
Hold YYYY to use deck XX
Press L to nullify Negitive Status Effects (Wifi)
Infinite Jumps+Air actions (wifi)
Press SELECT to end the game (wifi)
Press Start to push the time back to 99 (wifi)

Note about the wifi code: for some reason you will get desynced from the game if you do anything out of the ordinary like 4 jumps
so once you get to the results screen it will just crash,it probably won't happpen if both of you are using the codes though...

Game Code AJUJ Game ID 65e1d889

Hold L to unlock all komas (on menu)
94000130 fdff0000
d5000000 ffffffff
c0000000 0000001c
d6000000 020b0bac
d2000000 00000000

Hold B to unlock all courses (on menu)
94000130 fffd0000
020b0c93 ffffffff
d2000000 00000000
Note:Needs Testing

Infinite Air Jumps+ air attacks
b2181b28 00000000
200000d9 00000000
200000da 00000000
d2000000 00000000

Immmune to most negitive status effects
b2181b28 00000000
200000a0 00000000
d2000000 00000000

Have Postive Status XX
b2181b28 00000000
20000088 000000XX
d2000000 00000000
00=Nothing
09=Invicibility (doesn't actually give any effect)

Glitch the Battle Koma Sprites
021db611 000000ff
021db609 000000ff
Note: Most noticable in 1v1s

Hold L to fill the side thing with the komas you want
94000130 fdff0000
0228aab0 021eXXXX
0228aab4 021eXXXX
0228aab8 021eXXXX
0228aabc 021eXXXX
0228aac0 021eXXXX
0228aac4 021eXXXX
d2000000 00000000
(XXXX = koma id; start on a BLANK deck, deck grid on the bottom screen, hold L.
Only one of the same koma allowed.)

Koma id list (name, koma count, XXXX):
Tsuna 1:04c0 2:04cc 3:04d8 4:04e4 5:04f0 6:04fc 6:0508
Gintoki 1:0694 2:06a0 3:06ac 4:06b8 5:06c4 6:06d0 6:06dc 7:06e8
Kagura 1:06f4 2:0700 3:070c 4:0718 5:0724 6:0730 6:073c
Kinnikuman 1:085c 2:0868 3:0874 4:0880 4:088c 5:0898 6:08a4 7:08b0 8:08bc
Ryotsu 1:09dc 2:09e8 3:09f4 4:0a00 4:0a0c 5:0a18 6:0a24 7:0a30 8:0a3c
Edajima 1:0C10 8:0C1c
Momotaro 1:0c28 2:0c34 3:0c40 4:0c4c 5:0c58 6:0c64 6:0c70
Yoh 1:0d9c 2:0da8 3:0db4 4:0dc0 4:0dcc 5:0dd8 6:0de4
Anna 1:0df0 2:0dfc 3:0e08 4:0e14 5:0e20 5:0e2c
Jotaro 1:0ee0 2:0eec 3:0ef8 4:0f04 5:0f10 5:0f1c 6:0f28
Dio 1:0f34 2:0f40 3:0f4c 4:0f58 5:0f64 5:0f70 6:0f7c
Seiya 1:1114 2:1150 3:115c 4:1168 5:1174 6:1180 7:118c 8:1198
Allen 1:13e4 2:13f0 3:13fc 4:1408 5:1414 6:1420 6:142c
Lenalee 1:1438 2:1444 3:1450 4:145c 5:1468
Arale 1:15c4 2:15d0 3:15dc 4:15e8 5:15f4 6:1600 6:160c 7:1618
Dr.Mashirito 1:1624 2:1630 3:163c 4:1648 4:1654 5:1660 6:166c 7:1678 8:1684
Goku 1:1738 2:1744 3:1750 4:175c 4:1768 5:1774 6:1780 7:178c 8:1798
Vegeta 1:17a4 2:17b0 3:17bc 4:17c8 5:17d4 5:17e0 6:17ec
Gohan 1:17f8 2:1804 3:1810 4:181c 5:1828
Gotenks 1:1834 2:1840 3:184c 4:1858 5:1864 5:1870
Piccolo 1:187c 2:1888 3:1894 4:18a0 5:18ac
Frieza 1:18b8 2:2b78 6:18c4
Boo 1:18d0 6:18dc 6:18e8
Naruto 1:196c 2:1978 3:1984 4:1990 4:199c 5:19a8 6:19b4 7:19c0 8:19cc
Sasuke 1:19d8 7:19e4 8:19f0 8:19fc
Sakura 1:1a08 2:1a14 3:1a20 4:1a2c 5:1a38 6:1a44 6:1a50
Kakashi 1:1a5c 2:1a68 3:1a74 4:1a80 5:1a8c 6:1a98 6:1aa4
Fuusuke 1:1b04 2:1b10 3:1b1c 4:1b28 5:1b34 5:1b40
Gon 1:1b64 2:1b70 3:1b7c 4:1b88 5:1b94 6:1ba0
Killua 1:1bac 2:1bb8 3:1bc4 4:1bd0 5:1bdc
Jaguar 1:1c6c 2:1c78 3:1c84 4:1c90 5:1c9c 6:1ca8
Kazuki 1:1d44 2:1d50 3:1d5c 4:1d68 5:1d74 6:1d80
Eve 1:1db0 2:1dbc 3:1dc8 4:1dd4 5:1de0
Train 1:1dec 2:1df8 3:1e04 4:1e10 5:1e1c 5:1e28
Ichigo 1:1e70 2:1e7c 3:1e88 4:1e94 5:1ea0 6:1eac 7:1eb8 8:1ec4
Rukia 1:1ed0 2:1edc 3:1ee8 4:1ef4 5:1f00 6:1f0c
Renji 1:1f18 2:1f24 3:1f30 4:1f3c 5:1f48 6:1f54
Hitsugeya 1:1f60 2:1f6c 3:1f78 4:1f84 5:1f90 6:1f9c
Taikoubou 1:20e0 2:20ec 3:20f8 4:2104 5:2110 6:211c 6:2128
Kenshiro 1:2170 2:217c 3:2188 4:2194 5:21a0 6:21ac 7:21b8 8:21c4
Raoh 1:21d0 6:21e8 7:21f4 8:2200
Bo-BoBo 1:226c 2:2278 3:2284 4:2290 5:229c 6:22a8 6:22b4 7:22c0
Don Patch 1:22cc 2:22d8 3:22e4 4:22f0 5:22fc 6:2308 7:2314
Neuro 1:23f8 2:2404 3:2410 4:241c 4:2428 5:2434
Muhyo 1:24b8 2:24c4 3:24d0 4:24dc 5:24e8 6:24f4 7:2500
Yugioh 1:25b4 2:25c0 3:25cc 4:25d8 5:25e4 6:25f0
Yusuke 1:2644 2:2650 3:265c 4:2668 5:2674 6:2680
Kurama 1:268c 2:2698 3:26a4 4:26b0 5:26bc
Hiei 1:26c8 2:26d4 3:26e0 4:26ec 5:26f8
Kenshin 1:2740 2:274c 3:2758 4:2764 5:2770 6:277c 6:2788
Luffy 1:2890 2:289c 3:28a8 4:28b4 5:28c0 6:28cc 6:28d8 7:28e4 8:28f0
Zoro 1:28fc 2:2908 3:2914 4:2920 5:292c 5:2938 6:2944
Nami 1:2950 2:295c 3:2968 4:2974 4:2980 5:298c 6:2998
Sanji 1:29a4 2:29b0 3:29bc 4:29c8 5:29d4 5:29e0 6:29ec
Nico Robin 1:29f8 2:2a04 3:2a10 4:2a1c 5:2a28 6:2a34
Franky 1:2a40 2:2a4c 3:2a58 4:2a64 5:2a70 5:2a7c
Betas Battle Komas (4 koma square): Red koma man 2b30, Green 2b3c, yellow 2b48, Taizo mote 2bb4
Beta Support Komas (2 koma horizontal): Frieza 2b78, Boo 2b84, Sasuke 2b90, Raoh 2b9c, Edjima 2ba8, Carmel J man 2bcc
Beta Help Komas: Help A 2ae8, Help B 2af4, Help C 2b00, Red koma man (help) 2b0c, Green 2b18, Yellow 2b24

Color mods (Press B / Hold L; base b23d7b00, bytes +0x02..+0x22) omitted here: cosmetic only.

Defense never wears
b2181b28 00000000
20000102 00000000
d2000000 00000000

Press SELECT to end the game
94000130 FFFB0000
121dea70 00000000
d2000000 00000000

Press Start to push the time back to 99
94000130 FFF70000
121dea70 00000000
d2000000 00000000

Infinite Health
221df1d5 00000040
221df225 00000040
221df275 00000040
221df2c5 00000040

Always considered to be on the Ground
b23d2a74 00000000
b0000010 00000000
20000078 00000022
d2000000 00000000

Always considered to be in the Air (use with infinite jumps for awesomness)
b23d2a74 00000000
b0000010 00000000
20000078 00000000
d2000000 00000000

Hold YYYY to use deck XX
94000130 YYYY0000
020afeb4 XX XX XX XX
d20000000 0000000
XX: 00 deck 1, 08 deck 9, 0f deck 16, 10 deck 17, 13 deck 20
YYYY: fff6 START+A, fff5 START+B, fff4 START+SELECT, fbf7 START+X, f7f7 START+Y

Press L to nullify Negitive Status Effects (Wifi)
94000130 fdff0000
b21e2a7c 00000000
200000a0 00000000
d2000000 00000000
(repeated for b21e2a80, b21e2a84, b21e2a88)

Infinite Jumps+Air actions (wifi)
94000130 fffe0000
b21e2a7c 00000000
200000d9 00000000
200000da 00000000
d2000000 00000000
(repeated for b21e2a80, b21e2a84, b21e2a88)
Note: do not push A on any of the menus or else it will crash in the lobby, use the touch screen.

Press SELECT to end the game (wifi)
94000130 FFFb0000
121e29b0 00000000
d2000000 00000000

Press Start to push the time back to 99 (wifi)
94000130 FFF70000
121e29b0 0000ffff
d2000000 00000000

--- second source, same thread ---

Unlimited Time: 221DEA71 00000099

Unlimited Health
E2000000 00000010
E1D411F6 E1C411B8
E1A00000 EA01E13B
520784FC E1D411F8
020784FC EAFE1EBF
D2000000 00000000

Unlimited Special Attacks (Press X)
94000136 FFFE0000
221DF731 00000009
221DF8B1 00000009
D2000000 00000000

(Leader) Refill Health (Select + Down)
94000130 FF7B0000
221DF1D5 00000050
D2000000 00000000

(Non-leader) Refill Health (Select + Up)
94000130 FFBB0000
221df225 00000050
D2000000 00000000
```
