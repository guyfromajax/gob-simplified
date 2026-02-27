export function onAction(action, sprite, timestamp) {
    const scene = sprite.scene;
    if (!scene || !sprite) return;
  
    switch (action) {
      case "handle_ball":
        // Scale tweens removed (sunset) — no effect
        break;

      case "pass":
        // Scale tweens removed (sunset) — no effect
        break;

      case "receive":
        // Small bounce effect
        scene.tweens.add({
          targets: sprite,
          y: sprite.y - 10,
          duration: 100,
          yoyo: true,
          ease: "Sine.easeOut"
        });
        break;
  
      case "screen":
        // Flash red border or shake
        scene.tweens.add({
          targets: sprite,
          angle: 5,
          duration: 60,
          yoyo: true,
          repeat: 2,
          ease: "Linear"
        });
        break;
  
      case "shoot":
        // Scale tweens removed (sunset) — no effect
        break;

      case "steal":
        // Brief flash to highlight defender
        scene.tweens.add({
          targets: sprite,
          alpha: 0.5,
          duration: 100,
          yoyo: true,
          ease: "Sine.easeInOut"
        });
        break;

      default:
        // No effect for unrecognized actions
        break;
    }
  }
  