// Dialogue System — Text box for NPC interaction and story
// Defines global Dialogue object
// Dependencies: G, STATE, Util from utils.js, SFX from audio.js, Input from input.js

const Dialogue = {
  active: false,
  current: null,
  typeSpeed: 30, // characters per second
  previousGameState: null,

  start(dialogueData) {
    this.active = true;
    this.previousGameState = G.gameState;
    G.gameState = STATE.DIALOGUE;

    this.current = {
      npcName: dialogueData.npcName || 'Unknown',
      npcColor: dialogueData.npcColor || '#888888',
      lines: dialogueData.lines || [],
      lineIndex: 0,
      charIndex: 0,
      typing: true,
      choices: null,
      choiceIndex: 0
    };

    SFX.playSound('menu_select');
  },

  update(dt) {
    if (!this.active || !this.current) return;

    const line = this.current.lines[this.current.lineIndex];
    if (!line) {
      this.close();
      return;
    }

    // Typewriter effect
    if (this.current.typing) {
      this.current.charIndex += this.typeSpeed * dt;

      const text = typeof line === 'string' ? line : line.text;
      if (this.current.charIndex >= text.length) {
        this.current.charIndex = text.length;
        this.current.typing = false;

        // Check if this line has choices
        if (line.choices) {
          this.current.choices = line.choices;
          this.current.choiceIndex = 0;
        }
      }
    }

    // Input handling
    const skipPressed = Input.justPressed('Space') || Input.justPressed('Enter') ||
                        (Input.mouse && Input.mouse.clicked);

    if (skipPressed) {
      if (this.current.typing) {
        // Skip to end of current line
        const text = typeof line === 'string' ? line : line.text;
        this.current.charIndex = text.length;
        this.current.typing = false;

        if (line.choices) {
          this.current.choices = line.choices;
          this.current.choiceIndex = 0;
        }
      } else if (this.current.choices) {
        // Select current choice
        this.selectChoice(this.current.choiceIndex);
      } else {
        // Advance to next line
        this.nextLine();
      }
    }

    // Choice navigation
    if (this.current.choices && !this.current.typing) {
      if (Input.justPressed('ArrowUp') || Input.justPressed('w')) {
        this.current.choiceIndex = Math.max(0, this.current.choiceIndex - 1);
        SFX.playSound('menu_move');
      }
      if (Input.justPressed('ArrowDown') || Input.justPressed('s')) {
        this.current.choiceIndex = Math.min(
          this.current.choices.length - 1,
          this.current.choiceIndex + 1
        );
        SFX.playSound('menu_move');
      }
    }
  },

  nextLine() {
    this.current.lineIndex++;
    this.current.charIndex = 0;
    this.current.typing = true;
    this.current.choices = null;

    if (this.current.lineIndex >= this.current.lines.length) {
      this.close();
    } else {
      SFX.playSound('menu_select');
    }
  },

  selectChoice(index) {
    const choice = this.current.choices[index];
    if (!choice) return;

    SFX.playSound('menu_confirm');

    // Apply choice effects
    if (choice.effect) {
      this.applyChoiceEffect(choice.effect);
    }

    // Set story flag
    if (choice.flag) {
      G.storyChoices = G.storyChoices || {};
      G.storyChoices[choice.flag] = true;
    }

    // Give item
    if (choice.giveItem && window.Inventory) {
      const item = this.createChoiceItem(choice.giveItem);
      if (item) {
        Inventory.addItem(item);
      }
    }

    // Navigate to next dialogue or close
    if (choice.next) {
      this.current.lineIndex = choice.next;
      this.current.charIndex = 0;
      this.current.typing = true;
      this.current.choices = null;
    } else {
      this.close();
    }
  },

  applyChoiceEffect(effect) {
    if (effect.heal && window.Player) {
      Player.heal(effect.heal);
    }
    if (effect.damage && window.Player) {
      G.player.hp -= effect.damage;
    }
    if (effect.gold) {
      G.player.gold = (G.player.gold || 0) + effect.gold;
    }
  },

  createChoiceItem(itemId) {
    // Simple item creation for dialogue rewards
    if (window.CONSUMABLES) {
      const consumable = CONSUMABLES.find(c => c.id === itemId);
      if (consumable) {
        return {
          id: consumable.id,
          name: consumable.name,
          type: 'consumable',
          rarity: consumable.rarity,
          description: consumable.description,
          spriteColor: consumable.color,
          stackable: true,
          count: 1
        };
      }
    }
    return null;
  },

  close() {
    this.active = false;
    this.current = null;
    G.gameState = this.previousGameState || STATE.PLAYING;
    this.previousGameState = null;
  },

  render(ctx) {
    if (!this.active || !this.current) return;

    const canvas = ctx.canvas;
    const boxWidth = canvas.width * 0.8;
    const boxHeight = 150;
    const boxX = (canvas.width - boxWidth) / 2;
    const boxY = canvas.height - boxHeight - 20;

    // Draw semi-transparent background
    ctx.fillStyle = Util.rgba('#000000', 0.85);
    ctx.fillRect(boxX, boxY, boxWidth, boxHeight);

    // Draw border with gradient
    const gradient = ctx.createLinearGradient(boxX, boxY, boxX + boxWidth, boxY + boxHeight);
    gradient.addColorStop(0, this.current.npcColor);
    gradient.addColorStop(1, Util.rgba(this.current.npcColor, 0.3));
    ctx.strokeStyle = gradient;
    ctx.lineWidth = 3;
    ctx.strokeRect(boxX, boxY, boxWidth, boxHeight);

    // Draw NPC name header
    ctx.fillStyle = this.current.npcColor;
    ctx.fillRect(boxX, boxY - 30, 200, 30);
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 16px monospace';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.shadowColor = this.current.npcColor;
    ctx.shadowBlur = 8;
    ctx.fillText(this.current.npcName, boxX + 10, boxY - 15);
    ctx.shadowBlur = 0;

    // Draw portrait (simple colored circle with initial)
    const portraitX = boxX + 20;
    const portraitY = boxY + 30;
    const portraitRadius = 25;
    ctx.fillStyle = this.current.npcColor;
    ctx.beginPath();
    ctx.arc(portraitX, portraitY, portraitRadius, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 24px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(this.current.npcName.charAt(0).toUpperCase(), portraitX, portraitY + 2);

    // Draw dialogue text
    const textX = boxX + 70;
    const textY = boxY + 20;
    const textWidth = boxWidth - 90;

    const line = this.current.lines[this.current.lineIndex];
    const text = typeof line === 'string' ? line : line.text;
    const displayText = text.substring(0, Math.floor(this.current.charIndex));

    ctx.fillStyle = '#ffffff';
    ctx.font = '14px monospace';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';

    // Word wrap
    const words = displayText.split(' ');
    let currentLine = '';
    let lineY = textY;
    const lineHeight = 18;

    for (const word of words) {
      const testLine = currentLine + word + ' ';
      const metrics = ctx.measureText(testLine);
      if (metrics.width > textWidth && currentLine.length > 0) {
        ctx.fillText(currentLine, textX, lineY);
        currentLine = word + ' ';
        lineY += lineHeight;
      } else {
        currentLine = testLine;
      }
    }
    ctx.fillText(currentLine, textX, lineY);

    // Draw blinking cursor if still typing
    if (this.current.typing && Math.floor(Date.now() / 500) % 2 === 0) {
      const cursorX = textX + ctx.measureText(currentLine).width;
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(cursorX, lineY, 2, 14);
    }

    // Draw choices if present
    if (this.current.choices && !this.current.typing) {
      const choiceX = textX;
      let choiceY = boxY + 80;

      this.current.choices.forEach((choice, i) => {
        const isSelected = i === this.current.choiceIndex;
        ctx.fillStyle = isSelected ? '#ffff00' : '#aaaaaa';
        ctx.font = isSelected ? 'bold 14px monospace' : '14px monospace';

        const prefix = isSelected ? '> ' : '  ';
        ctx.fillText(prefix + choice.text, choiceX, choiceY);

        choiceY += 18;
      });
    }

    // Draw continue indicator
    if (!this.current.typing && !this.current.choices) {
      const indicatorText = 'Press SPACE to continue';
      const indicatorX = boxX + boxWidth - 10;
      const indicatorY = boxY + boxHeight - 10;

      ctx.fillStyle = Util.rgba('#ffffff', 0.3 + Math.sin(Date.now() / 300) * 0.3);
      ctx.font = '12px monospace';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'bottom';
      ctx.fillText(indicatorText, indicatorX, indicatorY);
    }
  }
};
