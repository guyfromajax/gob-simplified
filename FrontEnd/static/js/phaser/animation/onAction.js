export function onAction(action, sprite, timestamp) {
    const scene = sprite.scene;
    if (!scene || !sprite) return;
  
    switch (action) {
      case "handle_ball":
        // Light glow pulse
        scene.tweens.add({
          targets: sprite,
          scale: 1.1,
          duration: 150,
          yoyo: true,
          ease: "Sine.easeInOut"
        });
        break;
  
      case "pass":
        // Quick scale-out and in
        scene.tweens.add({
          targets: sprite,
          scale: 1.2,
          duration: 100,
          yoyo: true,
          ease: "Quad.easeInOut"
        });
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
        // Pop with delay (setup for future shot arc or animation)
        scene.tweens.add({
          targets: sprite,
          scale: 1.3,
          duration: 150,
          yoyo: true,
          ease: "Back.easeOut"
        });
        break;
  
      default:
        // No effect for unrecognized actions
        break;
    }
  }
  