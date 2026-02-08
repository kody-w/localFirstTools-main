// lore.js - Story, NPC dialogue, choices, and multiple endings for Depths of the Abyss
// Depends on: constants.js, utils.js

// Lore entries discovered throughout the game - tells the story of the Abyss
const LORE = [
  {
    floor: 1,
    id: 'entry_001',
    title: 'The Sealed Gate',
    text: 'The ancient seal has weakened. Something stirs in the depths below, calling to those foolish enough to listen. The gate that has held for a thousand years now cracks.',
    discovered: false,
    category: 'history'
  },
  {
    floor: 2,
    id: 'entry_002',
    title: 'First Descent',
    text: 'Many have descended before you, seeking glory or answers. None have returned. Their bones now guard the halls they sought to conquer.',
    discovered: false,
    category: 'warning'
  },
  {
    floor: 3,
    id: 'entry_003',
    title: 'The Old Sage',
    text: 'A wise hermit has made camp here. He speaks of ancient gods and forgotten prisons. "Turn back," he warns, "before you learn what lies below."',
    discovered: false,
    category: 'npc'
  },
  {
    floor: 5,
    id: 'entry_004',
    title: 'The Grave Warden',
    text: 'The first guardian has fallen. But you sense this is merely the beginning. The Abyss tests all who enter, and you have passed only the first trial.',
    discovered: false,
    category: 'boss'
  },
  {
    floor: 6,
    id: 'entry_005',
    title: 'Fungal Corruption',
    text: 'The fungus here is not natural. It feeds on death and spreads like a plague. The mycelia whisper secrets to those who listen too closely.',
    discovered: false,
    category: 'environment'
  },
  {
    floor: 7,
    id: 'entry_006',
    title: 'Network of Minds',
    text: 'The mushrooms are connected, a single consciousness spread across millions of fruiting bodies. It remembers every death in these caverns.',
    discovered: false,
    category: 'mystery'
  },
  {
    floor: 8,
    id: 'entry_007',
    title: 'The Lost Knight',
    text: 'You meet a warrior who came before. "I defeated the Warden," he says, "but the King broke me. Each floor grows harder. Each boss more terrible."',
    discovered: false,
    category: 'npc'
  },
  {
    floor: 10,
    id: 'entry_008',
    title: 'Mycelium King',
    text: 'The fungal hivemind had a leader, and you have destroyed it. Yet you wonder: can a network ever truly die? Already new spores spread in the darkness.',
    discovered: false,
    category: 'boss'
  },
  {
    floor: 11,
    id: 'entry_009',
    title: 'Descent into Fire',
    text: 'Heat rises from below. The stone itself glows with inner fire. You are approaching the heart of a volcano, or something far worse.',
    discovered: false,
    category: 'environment'
  },
  {
    floor: 12,
    id: 'entry_010',
    title: 'Ancient Forges',
    text: 'These were once halls of creation where legendary weapons were forged. Now only demons and fire remain, guarding secrets best forgotten.',
    discovered: false,
    category: 'history'
  },
  {
    floor: 13,
    id: 'entry_011',
    title: 'The Witch',
    text: 'A mysterious figure offers you power through dark rituals. "Help me," she pleads, "and I will grant you strength to face what lies ahead." But at what cost?',
    discovered: false,
    category: 'npc'
  },
  {
    floor: 15,
    id: 'entry_012',
    title: 'Infernal Colossus',
    text: 'The titan of flame has fallen. The fires dim, but you feel the heat of something deeper still. The true depths await below the molten stone.',
    discovered: false,
    category: 'boss'
  },
  {
    floor: 16,
    id: 'entry_013',
    title: 'Eternal Winter',
    text: 'The cold here defies nature. Time itself seems frozen. Crystals of ice preserve the dead in perfect stillness, waiting for something.',
    discovered: false,
    category: 'environment'
  },
  {
    floor: 17,
    id: 'entry_014',
    title: 'Time Stands Still',
    text: 'The deeper you go, the slower time flows. Seconds stretch to minutes. You age not, but the world above continues without you.',
    discovered: false,
    category: 'mystery'
  },
  {
    floor: 18,
    id: 'entry_015',
    title: 'Forbidden Knowledge',
    text: 'A scholar frozen in time offers you truth. "The Abyss is a prison," he reveals, "built to contain a god that refused to die. You walk the halls of its tomb."',
    discovered: false,
    category: 'npc'
  },
  {
    floor: 20,
    id: 'entry_016',
    title: 'Glacial Sovereign',
    text: 'The ice queen has shattered. With her defeat, time flows again. But you realize now that each guardian was a lock, and you have been opening them all.',
    discovered: false,
    category: 'boss'
  },
  {
    floor: 21,
    id: 'entry_017',
    title: 'The Void Beyond',
    text: 'You have passed beyond ice, fire, earth and flesh. This is the void between realities. The spaces where things that should not be wait in eternal darkness.',
    discovered: false,
    category: 'environment'
  },
  {
    floor: 22,
    id: 'entry_018',
    title: 'Truth of the Prison',
    text: 'The ancient god was not evil, only too powerful. When it refused mortality, the old gods sealed it here, in layers of elemental guardians and temporal barriers.',
    discovered: false,
    category: 'revelation'
  },
  {
    floor: 23,
    id: 'entry_019',
    title: 'The Final Choice',
    text: 'The Watcher appears. "You can seal the prison anew," it offers, "or take the god\'s power for yourself. But know this: either choice will change you forever."',
    discovered: false,
    category: 'npc'
  },
  {
    floor: 24,
    id: 'entry_020',
    title: 'The Last Guardian',
    text: 'Only one barrier remains. Beyond it lies the imprisoned god, still alive after millennia. It knows you are coming. It has been waiting for someone strong enough.',
    discovered: false,
    category: 'warning'
  },
  {
    floor: 25,
    id: 'entry_021',
    title: 'The Abyss Incarnate',
    text: 'You stand before a being beyond comprehension. It is not evil, not good. It simply IS. And it asks: "Why have you come? To destroy me? To free me? To become me?"',
    discovered: false,
    category: 'boss'
  }
];

// NPC dialogue trees with branching conversations and tutorial information
const NPC_DIALOGUES = {
  old_sage: {
    npcId: 'old_sage',
    name: 'Old Sage',
    floor: 3,
    portrait: 'sage',
    color: '#9370DB',
    greeting: 'Ah, another soul drawn to the depths. Sit, rest. Let me share what little wisdom I have.',
    dialogueTree: {
      start: {
        text: 'I have camped here for many years, guiding those who will listen. Most do not. They rush to their doom below.',
        responses: [
          { text: 'Can you teach me how to survive?', next: 'tutorial', effect: null },
          { text: 'What lies in the depths?', next: 'lore', effect: null },
          { text: 'How do I get stronger?', next: 'progression', effect: null },
          { text: 'I must press on.', next: 'farewell', effect: null }
        ]
      },
      tutorial: {
        text: 'Listen well to these instructions. Controls are simple but mastery takes time. WASD to move, mouse to aim, left click to attack. Space to dodge - timing is everything. Press I for inventory, K for skills. Watch your stamina - fighting recklessly will get you killed.',
        responses: [
          { text: 'Tell me about combat.', next: 'combat_tutorial', effect: null },
          { text: 'What about items and equipment?', next: 'items_tutorial', effect: null },
          { text: 'Thanks, I understand.', next: 'start', effect: null }
        ]
      },
      combat_tutorial: {
        text: 'Every weapon has range, speed, and stamina cost. Fast weapons let you dodge more but deal less damage. Slow weapons hit hard but leave you exposed. Learn enemy patterns - each has behaviors you can exploit. Combo attacks for bonus damage. Chain critical strikes for a multiplier.',
        responses: [
          { text: 'How do I defeat bosses?', next: 'boss_tutorial', effect: null },
          { text: 'What about difficulty?', next: 'difficulty_tutorial', effect: null },
          { text: 'Got it. What else?', next: 'tutorial', effect: null }
        ]
      },
      items_tutorial: {
        text: 'Loot drops from enemies and chests. Equip weapons and armor to grow stronger. Higher rarity means better stats - common, uncommon, rare, epic, legendary. Upgrade items at campfires. Save consumables for boss fights - you will need them.',
        responses: [
          { text: 'Tell me about abilities.', next: 'ability_tutorial', effect: null },
          { text: 'Anything else I should know?', next: 'tutorial', effect: null }
        ]
      },
      ability_tutorial: {
        text: 'Unlock skills by leveling up and spending skill points. Three paths: Warrior for power, Mage for magic, Rogue for speed. Each tier requires previous abilities. Choose wisely - you cannot unlock everything. Passive abilities always active. Active abilities use mana or stamina.',
        responses: [
          { text: 'What is the best build?', next: 'build_advice', effect: null },
          { text: 'Thanks for the help.', next: 'start', effect: null }
        ]
      },
      boss_tutorial: {
        text: 'Every fifth floor has a boss. They are stronger than anything before them. Multi-phase fights - tactics change as their health drops. Learn their patterns. Use the environment. Elite enemies appear randomly with better stats and loot. Mini-bosses guard key areas.',
        responses: [
          { text: 'How do I know the difficulty?', next: 'difficulty_tutorial', effect: null },
          { text: 'I am ready.', next: 'start', effect: null }
        ]
      },
      difficulty_tutorial: {
        text: 'The Abyss scales in difficulty. Easy floors ease you in. Medium tests your skills. Hard demands mastery. Elite enemies have enhanced stats. Deeper floors spawn tougher opponents. Adapt your strategy or perish.',
        responses: [
          { text: 'Understood.', next: 'start', effect: null }
        ]
      },
      build_advice: {
        text: 'No perfect path exists. Warriors survive through strength. Mages control with range and power. Rogues excel with speed and precision. Hybrid builds are possible but master one tree first. Adapt to your play style.',
        responses: [
          { text: 'Thanks for the advice.', next: 'start', effect: null }
        ]
      },
      lore: {
        text: 'These depths were once a temple, then a tomb, now a prison. Sealed within is a god that refused to die when the age of gods ended. Four guardians lock the way. You have already begun breaking the seals.',
        responses: [
          { text: 'Can the god be killed?', next: 'god_question', effect: null },
          { text: 'Tell me something else.', next: 'start', effect: null }
        ]
      },
      god_question: {
        text: 'Perhaps. Or perhaps it can only be imprisoned again. Or perhaps... you will make a different choice when the time comes.',
        responses: [
          { text: 'Cryptic as always.', next: 'start', effect: null }
        ]
      },
      progression: {
        text: 'Defeat enemies for experience. Level up to grow stronger and unlock new abilities. Better loot drops from elite enemies and bosses. Upgrade your equipment. Learn your skill tree. Only through power can you face what awaits below.',
        responses: [
          { text: 'Anything else?', next: 'start', effect: null }
        ]
      },
      farewell: {
        text: 'Then go. May your blade stay sharp and your will unbroken. I will be here if you return... if you can return.',
        responses: []
      }
    }
  },

  lost_knight: {
    npcId: 'lost_knight',
    name: 'Lost Knight',
    floor: 8,
    portrait: 'knight',
    color: '#C0C0C0',
    greeting: 'Another warrior descends. Good. The Abyss hungers for strong souls.',
    dialogueTree: {
      start: {
        text: 'I came here seeking glory. I defeated the Grave Warden easily. The Mycelium King... it broke me. I barely survived. Now I camp here, too wounded to continue, too proud to retreat.',
        responses: [
          { text: 'Tell me about the bosses.', next: 'bosses', effect: null },
          { text: 'What happened to you?', next: 'story', effect: null },
          { text: 'Can I help you?', next: 'help', effect: null },
          { text: 'I will avenge you.', next: 'farewell', effect: null }
        ]
      },
      bosses: {
        text: 'Each boss guards a seal. The Warden is a warrior like us - honorable, predictable. The King is chaos incarnate, splitting and reforming. Beyond lies the Colossus of flame - massive and unstoppable. Then the Sovereign of ice - beautiful and merciless. Finally... the god itself.',
        responses: [
          { text: 'Any advice for fighting them?', next: 'boss_advice', effect: null },
          { text: 'What else should I know?', next: 'start', effect: null }
        ]
      },
      boss_advice: {
        text: 'Learn their phases. Bosses grow desperate as they weaken - more dangerous but more vulnerable. Save your best abilities for phase transitions. Stock consumables. Upgrade everything you can. And never, ever give up mid-fight.',
        responses: [
          { text: 'I won\'t fail.', next: 'start', effect: null }
        ]
      },
      story: {
        text: 'I was arrogant. I thought my strength enough. The King taught me humility through pain. Its spores infected my mind, showed me visions of futures that might be. I am... not the same.',
        responses: [
          { text: 'You survived. That is what matters.', next: 'comfort', effect: 'buff_knight_morale' },
          { text: 'Weakness has no place here.', next: 'harsh', effect: null }
        ]
      },
      comfort: {
        text: 'Thank you. Your words mean more than you know. Here, take this. It may help you where I failed.',
        responses: [
          { text: 'I will use it well.', next: 'start', effect: 'receive_knight_gift' }
        ]
      },
      harsh: {
        text: 'Perhaps you are right. Perhaps I deserve my fate. Go then. May you prove stronger than I.',
        responses: [
          { text: 'I will.', next: 'farewell', effect: null }
        ]
      },
      help: {
        text: 'There is nothing you can do. My wounds run deeper than flesh. Continue your descent. Finish what I could not.',
        responses: [
          { text: 'I understand.', next: 'start', effect: null }
        ]
      },
      farewell: {
        text: 'Go. Prove that honor and strength still mean something in this cursed place.',
        responses: []
      }
    }
  },

  witch_of_spores: {
    npcId: 'witch_of_spores',
    name: 'Witch of Spores',
    floor: 13,
    portrait: 'witch',
    color: '#8B4789',
    greeting: 'Ah, a strong soul approaches. Perfect. I have need of such strength.',
    dialogueTree: {
      start: {
        text: 'I study the dark arts, seeking power to break the seals myself. But I lack the physical might. Help me gather reagents from the flame demons, and I will grant you forbidden power.',
        responses: [
          { text: 'What kind of power?', next: 'power', effect: null },
          { text: 'Why should I trust you?', next: 'trust', effect: null },
          { text: 'I will help you.', next: 'accept', effect: 'accept_witch_quest' },
          { text: 'I want no part of dark magic.', next: 'refuse', effect: 'refuse_witch_quest' }
        ]
      },
      power: {
        text: 'I can craft elixirs that enhance your abilities beyond natural limits. Strength, speed, resilience. I can enchant your weapons with dark fire. I know rituals to steal life from your enemies.',
        responses: [
          { text: 'That sounds dangerous.', next: 'danger', effect: null },
          { text: 'I accept your offer.', next: 'accept', effect: 'accept_witch_quest' },
          { text: 'No. I refuse.', next: 'refuse', effect: 'refuse_witch_quest' }
        ]
      },
      trust: {
        text: 'Trust? In the Abyss? How naive. I offer power, nothing more. Whether you use it for good or ill is your concern. But know that what awaits below will not hesitate to use every advantage against you.',
        responses: [
          { text: 'You make a fair point.', next: 'start', effect: null },
          { text: 'I still do not trust you.', next: 'distrust', effect: null }
        ]
      },
      danger: {
        text: 'All true power is dangerous. The question is whether you are strong enough to wield it without being consumed. Are you?',
        responses: [
          { text: 'I am. I will help.', next: 'accept', effect: 'accept_witch_quest' },
          { text: 'No. Too risky.', next: 'refuse', effect: 'refuse_witch_quest' }
        ]
      },
      accept: {
        text: 'Excellent. Bring me ember dust and dark crystals from the depths ahead. Return victorious, and I will fulfill my promise. This is the path to power.',
        responses: [
          { text: 'It shall be done.', next: 'farewell_help', effect: 'start_dark_path' }
        ]
      },
      refuse: {
        text: 'So be it. Face the flames unprepared then. Do not come crying to me when the Colossus burns you to ash. Fool.',
        responses: [
          { text: 'I will take my chances.', next: 'farewell_refuse', effect: 'start_light_path' }
        ]
      },
      distrust: {
        text: 'Your loss. Remember this moment when you face the guardians below and realize you lack the strength to win.',
        responses: [
          { text: 'We shall see.', next: 'farewell_refuse', effect: 'start_light_path' }
        ]
      },
      farewell_help: {
        text: 'Go. Embrace the darkness. It is the only way to survive what comes next.',
        responses: []
      },
      farewell_refuse: {
        text: 'Pathetic. Leave my sight.',
        responses: []
      }
    }
  },

  frozen_scholar: {
    npcId: 'frozen_scholar',
    name: 'Frozen Scholar',
    floor: 18,
    portrait: 'scholar',
    color: '#87CEEB',
    greeting: 'Finally. Someone who can hear me. I have waited so long...',
    dialogueTree: {
      start: {
        text: 'I came here centuries ago to study the prison. The ice preserved me, trapped me in a single moment. Now you have broken the Sovereign\'s hold, and I can speak again. You must know the truth.',
        responses: [
          { text: 'Tell me everything.', next: 'truth', effect: null },
          { text: 'What truth?', next: 'truth', effect: null },
          { text: 'I do not have time for this.', next: 'hasty', effect: null }
        ]
      },
      truth: {
        text: 'The god below is not evil. When the age of divinity ended, most gods accepted mortality and faded. This one refused. The remaining gods built this prison - four guardians, four seals, four elements. You have broken three.',
        responses: [
          { text: 'What happens when I break the fourth?', next: 'fourth_seal', effect: null },
          { text: 'Can the god be reasoned with?', next: 'reasoning', effect: null },
          { text: 'Should I stop?', next: 'should_stop', effect: null }
        ]
      },
      fourth_seal: {
        text: 'The god will be free to offer you a choice. Seal it again and save the world above. Destroy it and end its existence forever. Absorb its power and become something new. Or... there may be other paths. The scholar in me wants to know what you will choose.',
        responses: [
          { text: 'What would you choose?', next: 'scholar_choice', effect: null },
          { text: 'I will decide when the time comes.', next: 'future_choice', effect: null }
        ]
      },
      reasoning: {
        text: 'It has had millennia to think. To rage. To accept. To despair. What you find below will be beyond human understanding. But yes, it can communicate. It will try to sway you.',
        responses: [
          { text: 'I will listen with an open mind.', next: 'open_mind', effect: 'accept_knowledge' },
          { text: 'I will not be swayed.', next: 'closed_mind', effect: 'reject_knowledge' }
        ]
      },
      should_stop: {
        text: 'You cannot stop. The seals are breaking whether you continue or not. Your battles have weakened them all. The only question is whether you face what emerges prepared or unprepared.',
        responses: [
          { text: 'Then I press on.', next: 'continue', effect: null }
        ]
      },
      scholar_choice: {
        text: 'I would study it. Learn from it. But I am just a scholar, frozen in time. You are a warrior with the strength to reshape reality. The choice is yours alone.',
        responses: [
          { text: 'I understand.', next: 'future_choice', effect: null }
        ]
      },
      open_mind: {
        text: 'Wisdom. Take this knowledge with you. It may save you... or doom you. Either way, you will face the truth with eyes open.',
        responses: [
          { text: 'Thank you.', next: 'farewell_knowledge', effect: 'gain_forbidden_knowledge' }
        ]
      },
      closed_mind: {
        text: 'Stubbornness. Or perhaps wisdom. Sometimes ignorance is safer than knowledge. Go then, unburdened by doubt.',
        responses: [
          { text: 'Farewell.', next: 'farewell_ignorance', effect: null }
        ]
      },
      hasty: {
        text: 'Then go. Rush to your fate. But do not say you were not warned.',
        responses: []
      },
      future_choice: {
        text: 'Wise. Trust your instincts when the moment comes. They have brought you this far.',
        responses: [
          { text: 'I will.', next: 'farewell_knowledge', effect: null }
        ]
      },
      continue: {
        text: 'Then go. Face the Abyss. And may whatever you find there grant you the ending you deserve.',
        responses: [
          { text: 'I am ready.', next: 'farewell_knowledge', effect: null }
        ]
      },
      farewell_knowledge: {
        text: 'Good luck. You will need it. The void awaits.',
        responses: []
      },
      farewell_ignorance: {
        text: 'Go. Face your destiny unprepared. I cannot stop you.',
        responses: []
      }
    }
  },

  the_watcher: {
    npcId: 'the_watcher',
    name: 'The Watcher',
    floor: 23,
    portrait: 'watcher',
    color: '#4B0082',
    greeting: 'You have come far. But the true test lies ahead.',
    dialogueTree: {
      start: {
        text: 'I am the Watcher. I observe all who descend. I watched you break the seals, defeat the guardians, grow in power. Now you stand at the threshold. One floor remains. One choice awaits.',
        responses: [
          { text: 'What choice?', next: 'choice', effect: null },
          { text: 'Who are you really?', next: 'identity', effect: null },
          { text: 'I am ready to face the god.', next: 'ready', effect: null }
        ]
      },
      choice: {
        text: 'When you defeat the god - if you defeat it - you must choose its fate. Seal the prison anew and restore the old order. Absorb its power and become the new god. Show mercy and free it. Or destroy it utterly and end its existence.',
        responses: [
          { text: 'What are the consequences?', next: 'consequences', effect: null },
          { text: 'Which should I choose?', next: 'guidance', effect: null },
          { text: 'I will decide in the moment.', next: 'no_choice_yet', effect: null }
        ]
      },
      identity: {
        text: 'I am the first to descend. The first to face the god. I chose to watch, to wait, to guide those who come after. I am the price of balance. Forever between worlds.',
        responses: [
          { text: 'That sounds lonely.', next: 'lonely', effect: null },
          { text: 'What did you see when you faced the god?', next: 'watcher_vision', effect: null }
        ]
      },
      ready: {
        text: 'Confidence. Good. You will need it. But be warned - the god will test you in ways the guardians never could. It will offer you everything you desire. It will show you futures that could be.',
        responses: [
          { text: 'I will not be swayed.', next: 'strong_will', effect: null },
          { text: 'What did it offer you?', next: 'watcher_offer', effect: null }
        ]
      },
      consequences: {
        text: 'Seal it: the world is safe but unchanged. Absorb it: you gain ultimate power but lose your humanity. Free it: chaos, but also potential for something new. Destroy it: permanent victory, but the death of divinity itself.',
        responses: [
          { text: 'All paths have prices.', next: 'wisdom', effect: null },
          { text: 'There must be a right answer.', next: 'right_answer', effect: null }
        ]
      },
      guidance: {
        text: 'I cannot tell you. This choice defines you. I chose my path. The knight who came before chose his. The witch chose hers. You must choose yours.',
        responses: [
          { text: 'I understand.', next: 'no_choice_yet', effect: null }
        ]
      },
      lonely: {
        text: 'Yes. But necessary. Someone must remember. Someone must guide. That burden is mine.',
        responses: [
          { text: 'Thank you for your sacrifice.', next: 'gratitude', effect: null }
        ]
      },
      watcher_vision: {
        text: 'I saw myself as god. I saw the world burning. I saw endless possibilities. And I chose none of them. I chose to watch, to ensure others would have the choice I could not make.',
        responses: [
          { text: 'A noble sacrifice.', next: 'gratitude', effect: null }
        ]
      },
      strong_will: {
        text: 'Perhaps. We shall see. Many have said the same. All were tested. All were changed.',
        responses: [
          { text: 'I am different.', next: 'confidence', effect: null },
          { text: 'You may be right.', next: 'humility', effect: null }
        ]
      },
      watcher_offer: {
        text: 'It offered me everything. Power. Knowledge. The ability to reshape reality. And I saw the cost. I chose to refuse all paths and forge my own.',
        responses: [
          { text: 'Inspiring.', next: 'gratitude', effect: null }
        ]
      },
      wisdom: {
        text: 'Exactly. There is no perfect choice. Only the choice that is right for you, in that moment, with the knowledge you have.',
        responses: [
          { text: 'I will remember that.', next: 'farewell', effect: 'watcher_blessing' }
        ]
      },
      right_answer: {
        text: 'There is no right answer. Only your answer. Trust yourself.',
        responses: [
          { text: 'I will try.', next: 'farewell', effect: null }
        ]
      },
      gratitude: {
        text: 'Thank you. Few understand. Go now. Face your destiny. And may you find the ending you seek.',
        responses: [
          { text: 'Farewell.', next: 'farewell', effect: 'watcher_blessing' }
        ]
      },
      confidence: {
        text: 'Confidence will serve you well. But remain humble. Pride has destroyed stronger warriors than you.',
        responses: [
          { text: 'Noted.', next: 'farewell', effect: null }
        ]
      },
      humility: {
        text: 'Wisdom. Hold onto that humility. It will serve you when power tempts.',
        responses: [
          { text: 'I will.', next: 'farewell', effect: 'watcher_blessing' }
        ]
      },
      no_choice_yet: {
        text: 'Fair enough. Face the god first. Survive. Then decide. That is wisdom.',
        responses: [
          { text: 'Thank you.', next: 'farewell', effect: null }
        ]
      },
      farewell: {
        text: 'This is goodbye. Whatever you choose, know that I will watch. I will remember. Go. Complete your journey.',
        responses: []
      }
    }
  }
};

// Story choice tracking for multiple endings
const STORY_CHOICES = {
  witch_quest: {
    floor: 13,
    id: 'witch_quest',
    description: 'Help the Witch of Spores or refuse her dark magic',
    choices: ['help_witch', 'refuse_witch', 'betray_witch'],
    default: 'refuse_witch',
    value: 'refuse_witch'
  },
  knowledge_choice: {
    floor: 18,
    id: 'knowledge_choice',
    description: 'Accept or reject the Frozen Scholar\'s forbidden knowledge',
    choices: ['accept_knowledge', 'reject_knowledge'],
    default: 'reject_knowledge',
    value: 'reject_knowledge'
  },
  final_choice: {
    floor: 23,
    id: 'final_choice',
    description: 'Decide the fate of the imprisoned god',
    choices: ['seal_god', 'absorb_power', 'free_god', 'destroy_god'],
    default: null,
    value: null
  },
  boss_mercy: {
    floor: 25,
    id: 'boss_mercy',
    description: 'Show mercy or destroy the Abyss Incarnate',
    choices: ['show_mercy', 'destroy_utterly', 'negotiate'],
    default: null,
    value: null
  }
};

// Five distinct endings based on player choices throughout the game
const ENDINGS = {
  sealed_gate: {
    id: 'sealed_gate',
    name: 'The Sealed Gate',
    category: 'good',
    requirements: {
      final_choice: 'seal_god',
      witch_quest: 'refuse_witch',
      boss_mercy: 'show_mercy'
    },
    title: 'VICTORY: The Prison Holds',
    description: 'You have sealed the god once more. The Abyss is locked.',
    epilogue: 'You emerge from the depths, changed but whole. The seals hold stronger than before, reinforced by your will. The world above continues, safe and unaware of how close it came to ending. You saved everyone, and no one will ever know. Perhaps that is the truest victory.',
    flavorText: 'The gate is sealed. The world is safe. You have won.',
    endingType: 'victory'
  },

  new_god: {
    id: 'new_god',
    name: 'The New God',
    category: 'neutral',
    requirements: {
      final_choice: 'absorb_power',
      knowledge_choice: 'accept_knowledge'
    },
    title: 'VICTORY: Ascension',
    description: 'You have absorbed the divine power. You are no longer mortal.',
    epilogue: 'The power flows into you, transforming every cell. You are no longer human, no longer bound by mortality or time. You seal yourself in the Abyss willingly, becoming the new guardian. The prison needs a warden, and you are now eternal. You conquered the Abyss by becoming it. Congratulations, god.',
    flavorText: 'You have achieved victory over death itself. But at what cost?',
    endingType: 'victory'
  },

  dark_lord: {
    id: 'dark_lord',
    name: 'The Dark Lord',
    category: 'evil',
    requirements: {
      final_choice: 'absorb_power',
      witch_quest: 'help_witch',
      boss_mercy: 'destroy_utterly'
    },
    title: 'VICTORY(?): The Abyss Rises',
    description: 'You have taken the power for yourself and rejected mercy.',
    epilogue: 'The divine power corrupts as it empowers. You emerge not as a savior but as a conqueror. The world above will bow or burn. You escaped the Abyss, but the Abyss did not escape you. You have won everything and lost yourself. The new age of darkness begins with your first step into the light.',
    flavorText: 'You escaped the Abyss. But at what cost to the world?',
    endingType: 'victory'
  },

  martyr: {
    id: 'martyr',
    name: 'The Martyr',
    category: 'heroic',
    requirements: {
      final_choice: 'destroy_god',
      boss_mercy: 'destroy_utterly'
    },
    title: 'ULTIMATE VICTORY: The Final Sacrifice',
    description: 'You have destroyed the god utterly, ending divinity itself.',
    epilogue: 'To destroy a god, you must give everything. The power released in the god\'s death consumes you as well. The Abyss collapses, the prison unmade, the divine erased from reality. You die, but your sacrifice ends the threat forever. Generations to come will never know your name, never face what you faced, never have to make the choice you made. Congratulations. You saved them all.',
    flavorText: 'Ultimate victory requires ultimate sacrifice. You are the hero the world needed.',
    endingType: 'victory'
  },

  eternal_watcher: {
    id: 'eternal_watcher',
    name: 'The Eternal Watcher',
    category: 'balanced',
    requirements: {
      final_choice: 'free_god',
      knowledge_choice: 'accept_knowledge',
      boss_mercy: 'negotiate'
    },
    title: 'GAME COMPLETE: A New Beginning',
    description: 'You have freed the god and forged a new covenant.',
    epilogue: 'You and the god make a pact. It will not interfere with the mortal world, and you will ensure it keeps its word. Like the Watcher before you, you choose a third path - not seal, not absorb, not destroy, but coexist. You remain in the Abyss, eternal guardian of an eternal being. The depths become your home. Ending. And beginning.',
    flavorText: 'The game is complete. The cycle continues. The watch begins anew.',
    endingType: 'ending'
  }
};

// Utility functions for story system
const STORY_SYSTEM = {
  // Record player choice
  recordChoice(choiceId, value) {
    if (STORY_CHOICES[choiceId]) {
      STORY_CHOICES[choiceId].value = value;
    }
  },

  // Get player choice
  getChoice(choiceId) {
    return STORY_CHOICES[choiceId]?.value || STORY_CHOICES[choiceId]?.default;
  },

  // Check if ending requirements are met
  checkEnding(endingId) {
    const ending = ENDINGS[endingId];
    if (!ending || !ending.requirements) return false;

    for (let choiceId in ending.requirements) {
      const required = ending.requirements[choiceId];
      const actual = STORY_SYSTEM.getChoice(choiceId);
      if (actual !== required) return false;
    }

    return true;
  },

  // Determine which ending the player gets
  determineEnding() {
    // Check endings in priority order
    const priority = ['martyr', 'dark_lord', 'new_god', 'eternal_watcher', 'sealed_gate'];

    for (let endingId of priority) {
      if (STORY_SYSTEM.checkEnding(endingId)) {
        return ENDINGS[endingId];
      }
    }

    // Default ending if nothing matches
    return ENDINGS.sealed_gate;
  },

  // Unlock lore entry
  unlockLore(floor) {
    const entry = LORE.find(l => l.floor === floor);
    if (entry) {
      entry.discovered = true;
      return entry;
    }
    return null;
  },

  // Get all discovered lore
  getDiscoveredLore() {
    return LORE.filter(l => l.discovered);
  },

  // Get lore completion percentage
  getLoreCompletion() {
    const total = LORE.length;
    const discovered = LORE.filter(l => l.discovered).length;
    return Math.floor((discovered / total) * 100);
  }
};
