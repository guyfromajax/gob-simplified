# GOB Sonic Identity

> **Reviewed 2026-06-13 — creative design brief (no code-coupled claims to verify).** This is the audio north-star / direction doc; it makes no implementation claims, so there is nothing to drift against the codebase. Kept as-is on content; fixed malformed section headings (`##Heading` → `## Heading`) so they render correctly.

The single source of truth for every sound in Geeked-Out Basketball. Every prompt, every license decision, every approval reference this doc.

**The core principle**
GOB is a video game first, set inside an authentic basketball wrapper.
Not the other way around. We are not building a basketball simulation that happens to be a game. We are building a game that uses basketball as its world.

## What this means for sound:

    The video game layer is the foundation. Distinct, designed SFX communicate gameplay information — shot type, shot quality, momentum, decision quality. These sounds do not need to exist in real basketball. A weak outside shot and a strong outside shot can have meaningfully different sonic signatures even though no real basketball does that.
    The basketball layer punctuates and grounds. Whistles, rim/net/backboard, crowd reactions, sneaker squeaks, horns. These are the authentic moments that tether the video game to the sport.

    The two layers play together constantly. A shot release plays a designed "outside attempt" SFX; the rim sound that follows is authentic; the crowd reaction is authentic; the announcement sting is designed. Player hears all four in under two seconds and reads the whole moment without text.
    When in doubt about whether a sound should be designed or authentic, use this test: does the sound need to communicate gameplay information the user couldn't otherwise know? If yes, design it. If it's just the sound a thing makes in real life, keep it authentic.

## The world we're in
    GOB simulates high school basketball, but the audio reaches up toward a premium college feel. Our 128 teams span a wide range:

    Marquee programs (8K-12K attendance) — mid-major college arena energy. Full crowds, real bands, charged atmosphere.
    Mid-tier programs (1K-4K) — solid high school gym, decent crowd density, room reverb is more prominent because the room is smaller.
    Small programs (hundreds) — intimate gym, sparse crowd, every sneaker squeak audible, voices distinguishable in the crowd.



## Reference points
    Pull toward:

        Football Manager's approach to audio — designed, purposeful, never decorative
        The clarity of well-recorded documentary audio — every element legible
        Classic arcade and pinball sound design philosophy: each event has a distinct, recognizable signature
        For the basketball layer: CBS college broadcast acoustic warmth, circa 2010-2015
        The restraint of premium UI sound design (think Linear, Arc browser) for non-gameplay screens

    Pull away from:

        NBA 2K's over-mixed, hyper-compressed arcade thump
        EDM-inflected stingers, risers, "epic" cinematic hits
        Mobile game reward sounds — slot machines, candy crush, anything that screams "dopamine hit"
        Synthetic crowd loops that sound like one voice multiplied
        The boomy sub-heavy mix of modern NBA broadcasts
        Generic stock library "basketball game" SFX
        Sounds that announce themselves as designed when they should be invisible

## The two-layer model
    Every audible moment in GOB sits in one of three buckets:
    Designed video game layer — Shot release SFX (by type and quality), announcement stings, momentum indicators, decision-quality cues, non-gameplay UI, functional navigation. These are invented sounds. They follow a consistent design language but they're not trying to be real.
    Authentic basketball layer — Rim, net, backboard, ball-floor bounce, sneaker squeaks, whistles, horns, crowd reactions, ambient beds. These are real sounds, recorded or generated to sound recorded.

    Hybrid moments — Big made shot = designed swish-confirm SFX + authentic net sound + authentic crowd. The engine layers these. Files stay separate.
    This separation is non-negotiable. Designed sounds never get baked into authentic ones, and vice versa.

## The premium feeling
    Premium in GOB does not come from loudness, density, or production polish for its own sake. It comes from:

        Clarity — every sound has a clear role and a distinct frequency space.
        
        Headroom — sounds breathe. Dynamic range is protected so a clutch make can actually feel bigger than a routine one.
        
        Restraint — we underplay. A great rebound is a thud and a shuffle, not a five-element production.

        Cohesion — designed sounds share a family resemblance. Same synth voice, same envelope philosophy, same harmonic palette. A player should be able to recognize "that's a GOB sound" the way they recognize a Mario coin.

    If a sound feels "epic," it's wrong. If a designed sound feels gimmicky or arcade-y in the cheap sense, it's wrong. If a sound feels purposeful and clean, it's right.

## Sonic dimensions
    Every gameplay sound exists somewhere on these axes. Specify the position when prompting.

    Layer — designed / authentic / hybrid
    Intensity — weak / medium / strong (tied to shot quality, momentum, game state)
    Stakes — routine / mid-game / late-game / clutch
    Venue scale — marquee / mid-tier / small (applies to crowd and ambient layers only)
    Proximity — court-level / mid-room / room-wide
    Duration class — instant (<0.3s) / short (0.3-1.5s) / medium (1.5-5s) / bed (5s+, loopable)

## The design language of the video game layer
    This is the part that needs the most discipline, because it's the most invented. Some principles to lock in early:

        Shot-type sonic families. Outside, attack, and inside shots each get a distinct sonic signature on release. Outside might be brighter and more harmonic. Attack more percussive and forward-moving. Inside denser and lower. The three should be obviously different but clearly siblings — same instrument family, different notes.

        Weak is duller, shorter, slightly detuned. Strong is brighter, fuller, more resonant. Medium is the neutral baseline.

    No melodic content. Designed SFX use tonal material but should not feel like musical phrases. Pitched but not melodic. A note, not a hook.

    Synthesis over sampling. The designed layer should sound synthesized — clean, electronic, deliberate — not like processed real-world sounds. This is what gives it the "video game" identity.

    The GOB sonic palette (to refine through iteration): warm digital tones, subtle harmonic motion, short attacks, controlled decays. No FM-synth aggression, no chiptune retro, no orchestral hits.

## The design language of the authentic layer

    Reverb is real-room, not plate or hall. Short tails, natural decay.
    Recorded perspective — court-level for shots and floor sounds, mid-room for whistles, room-wide for horns and crowd.
    Crowd is scaled, not faked. Different bed densities for different venue scales rather than processing one bed.
    Frequency discipline. Rim in the mids, crowd in the lower-mids and highs, buzzers in the high-mids, sneakers in the top end.

## Acoustic rules (apply to both layers)

    Mono is the default for any court-level sound under 1 second. Stereo only when spatial width is meaningful.
    No baked-in mixing. Each file is one element. The engine layers.
    Trim aggressively. Zero leading silence. Tails decay naturally but don't linger.
    Loudness-match within categories, not across them. All shot releases are loudness-matched to each other. All rim sounds to each other. Designed and authentic layers stay separately matched.

## The negative space rule
    Silence is a design choice, not a default. The game should get quieter, not louder, at key moments — a Q4 timeout with the score tied drops the crowd to a tense murmur. A blowout's late minutes feel sparse. We earn the loud moments by protecting the quiet ones.
    If a screen, a moment, or a transition doesn't need sound, it doesn't get one.

## What every sound must do
    Before any file enters the library, it passes this checklist:

    Roled — clear job in the game experience. Sayable in one sentence.

    Layered correctly — designed, authentic, or intentionally hybrid. Never accidentally hybrid.

    Distinct — sounds different from every other sound in its category.

    On-brand — purposeful, restrained, cohesive with the rest of its layer.

    Layerable — clean enough for the engine to combine it without mud.

