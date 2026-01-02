**Hello**
Geeked-Out Basketball (GOB) is a state-heavy, turn-based basketball simulation built around deep coaching strategy, long-lived game instances, and strict persistence requirements. It supports multiple game modes: Single Game, Tournament, and Franchise, each with distinct user contexts and data lifecycles, including long-term progression and continuity in Franchise mode. Core gameplay and preparation systems (e.g., turn resolution, rebounding, fast breaks, training, scouting, game planning) operate across clearly defined instance types and depend on explicit state ownership, invariants, and persistence boundaries to remain stable as the system evolves.

**Our Principle As We Build***
SS&S (Simple, Stable, and Scalable)
Those three words speak for themselves. Every feature and line of code we add to, or remove from the codebase must in support of making this game engine more simple, stable, and scalable.
