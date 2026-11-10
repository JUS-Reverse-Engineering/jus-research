# Battle architecture for Rails developers

JUS does not put every aspect of an in-battle character into one object. The
running game links roster data, deck records, a live fighter object, movement
state, collision state, and move control. Shared managers update those parts in
a fixed order each simulation step. This page explains that structure through
Ruby and Rails examples. The Ruby names below are illustrative; they are not
classes or methods recovered from JUS.

For current facts about the original game, follow the linked references in
[`confirmed-facts/`](../confirmed-facts/).

## One character, several kinds of state

| JUS part | Imagine writing this in Rails | Where the analogy stops |
|---|---|---|
| Character data in `chr_b.bin` | `CharacterDefinition.find(7)` returns a roster entry with base nature and movement or damage tiers. Starting a match copies selected values into runtime state. | This is a compact binary file record, not an Active Record object. The same definition can supply many matches. The character-init copy is mapped in the [character-state research](Character-State-Struct.md). |
| Deck record | `match.team.members[1].hp` still exists when member 1 is on the bench. `match.team.members[0]` is the leader, while an `active?` flag identifies who is fighting. | The record holds match state, including HP, abilities, and regeneration. Its position does not tell you which member has a live fighter object. See the [deck-record identification](HP-And-Damage-Runtime-Findings.md). |
| Live fighter object | Think of `match.player_one.active_fighter` as the actor handling input, guard, hitstun, and action state. Switching members refills that actor with the incoming member's data. | The documented two-participant battle has two live fighter objects, while reserve members live in deck records. A switch reuses the live position and can wait for an interruptible action. See [fighter state](../confirmed-facts/physics.md) and [switch behavior](../confirmed-facts/deck-editor.md). |
| Pooled entity | `BattleEntity` would be a reusable runtime wrapper associated with the fighter and its collision state. A projectile can also obtain an entity from the pool. | The fighter and its entity point to each other. Entity construction wires collision; spawned-object attribution also uses a separate control wrapper. See [entities and ownership](../confirmed-facts/entities.md). |
| MoveMan element | `PhysicsBody` would hold `x`, `y`, velocity, acceleration, and impulses. `Battle#integrate_elements` would update both fighters' and projectiles' bodies. | Movement does not live entirely in a fighter method. The shared integrator visits elements and clears transient impulses each step. See [movement physics](../confirmed-facts/physics.md) and the [MoveMan reference](../confirmed-facts/moves.md). |
| ColPrm record | `CollisionState` might hold hit geometry and a `pending_damage` accumulator. The collision pass writes it; a later fighter update applies the result to HP. | One record is the entity's collision owner and the damage path's working storage. It also carries flags and knockback values. See the [collision record](../confirmed-facts/collision.md) and [damage structures](../confirmed-facts/damage.md). |
| NoteTrack | `MoveProgress` might hold active move instructions. `advance_if(contact_with_other_fighter?)` captures one kind of condition check. | Seven slots hold notes, and several note kinds share a slot and overwrite one another. A contact query can affect move progression. This is not a general event queue. See the [NoteTrack reference](../confirmed-facts/moves.md). |

The important Rails distinction is between a **definition**, a **member of this
match**, and the **actor currently on screen**. In a typical Rails application,
you might hang all three concepts off one `Character` model. JUS gives each a
different lifetime. The deck member can persist on the bench while the active
fighter changes. The movement and collision records are reused by shared
engine code.

## Follow one hit across the records

An input changes the fighter's action state. The state machine stages a
pending code and commits it during the fighter update. Action state and ground
or air condition are separate, so a fighter can be grounded while hitstun
locks control. See the [fighter-state reference](../confirmed-facts/physics.md).

An animation track then supplies a collision ID for its current frame. The ID
selects a built-in box or an authored 20-byte record from the character's
collision file. The record supplies properties such as damage class, hit type,
and knockback. The [collision reference](../confirmed-facts/collision.md)
documents the record selection and loading path.

The collision manager builds and processes contact pairs. Pair processing
computes damage and accumulates HP and SP contributions on the victim's ColPrm
record. NoteTrack can query contact results to decide whether a move
instruction advances. See the [collision pipeline](../confirmed-facts/collision.md),
[damage accumulation](../confirmed-facts/damage.md), and
[NoteTrack queries](../confirmed-facts/moves.md).

Timing is part of the contract. A logic step samples input, regenerates bench
members, updates fighters, updates projectiles, processes contacts, and then
integrates movement. Knockback affects movement in the contact frame. Pending
HP damage and the hitstun write reach the fighter update on the next logic
step, because that update already ran. A single `victim.take_damage(amount)`
call could reproduce the arithmetic while applying the effects in the wrong
order. The measured task order and its limits are in the
[per-frame task reference](../confirmed-facts/physics.md).

Projectiles use related infrastructure. A fixed pool supplies entities;
construction wires their collision state. An ObjShot element tracks kind and
lifetime and selects a kind-specific handler. Some kinds do not create a
separate pooled entity. See the [entity reference](../confirmed-facts/entities.md).

## Why the design might look this way

The recovered structures use bounded pools, recycled objects, compact records,
fixed-point arithmetic, and shared update paths. The collision manager has
128 ColPrm records, ObjShot has 72 element slots, and the contact queue has a
512-node pool. Character and attack variation comes substantially from data,
while code handles scheduling, state transitions, and contacts. See the
[collision manager](../confirmed-facts/collision.md),
[entity manager](../confirmed-facts/entities.md), and
[damage arithmetic](../confirmed-facts/damage.md).

It is reasonable to infer that bounded pools made memory use predictable,
recycling reduced allocation during play, and shared paths helped a large
roster use consistent mechanics. Fixed-point arithmetic also determines exact
rounding, which matters when reproducing how JUS plays. The repo does not
establish an original RAM budget, CPU benchmark, or developer statement that
proves which concern motivated a particular choice.

The result has some traits associated with component-based design, but its
objects are linked through pointers and managed by specific subsystems. It is
not a clean implementation of a modern ECS. The practical reading strategy is
to ask two questions for each value: **which record owns it, and at which
frame phase does another subsystem read it?**

`JUSToolkit` answers a different question: what the ROM files contain. Its C#
combat classes parse binary records, including the 60-byte `chr_b.bin` entry
and 20-byte collision entry. Some of their semantic property names are
tentative. Use those classes for file layout and the current facts in this
repo for runtime behavior.
