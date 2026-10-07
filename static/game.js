/* Chronicles of the Shattered Realm — client script.
 *
 * 1. In-place screens: forms are posted with fetch and the new .screen is swapped in,
 *    so the page (and the music) never reloads. Without JS the forms post normally.
 * 2. Sound effects: synthesized with the Web Audio API (no audio files). Taps play an
 *    action sound at once; messages that are *new* on the next screen play result sounds.
 * 3. Music: a small step sequencer playing generated themes. <body data-music> (set in
 *    game.html) picks the theme; town and explore themes follow the zone's mode.
 *
 * Browsers only allow audio after a user gesture, so nothing plays until the first tap.
 * Settings (music / sound on or off) live in localStorage.
 */
(function () {
  'use strict';

  // ── Settings ────────────────────────────────────────────────────────────────
  var settings = { music: true, sfx: true };
  try {
    var saved = JSON.parse(localStorage.getItem('rpg-audio') || '{}');
    if (typeof saved.music === 'boolean') settings.music = saved.music;
    if (typeof saved.sfx === 'boolean') settings.sfx = saved.sfx;
  } catch (e) { /* private mode etc. — defaults are fine */ }
  function saveSettings() {
    try { localStorage.setItem('rpg-audio', JSON.stringify(settings)); } catch (e) {}
  }

  // ── Audio graph ─────────────────────────────────────────────────────────────
  var AC = window.AudioContext || window.webkitAudioContext;
  var ctx = null, master, sfxBus, musicBus, noiseBuffer;
  var MUSIC_LEVEL = 0.3, SFX_LEVEL = 1.2;   // music sits under the effects (checked by rendering both)

  function build(c) {
    ctx = c;
    // Soft clipper instead of a compressor (DynamicsCompressor adds make-up gain): exactly
    // linear up to 0.6, then bends smoothly toward 0.9, so stacked sounds never clip.
    var clip = ctx.createWaveShaper(), curve = new Float32Array(2049);
    for (var k = 0; k < curve.length; k++) {
      var x = k / (curve.length - 1) * 2 - 1, a = Math.abs(x);
      curve[k] = a < 0.6 ? x : (x < 0 ? -1 : 1) * (0.6 + 0.4 * Math.tanh((a - 0.6) / 0.4));
    }
    clip.curve = curve;
    master = ctx.createGain(); master.gain.value = 0.9;
    master.connect(clip); clip.connect(ctx.destination);
    sfxBus = ctx.createGain(); sfxBus.gain.value = settings.sfx ? SFX_LEVEL : 0; sfxBus.connect(master);
    musicBus = ctx.createGain(); musicBus.gain.value = settings.music ? MUSIC_LEVEL : 0; musicBus.connect(master);
    var len = ctx.sampleRate;                      // one second of white noise, reused
    noiseBuffer = ctx.createBuffer(1, len, ctx.sampleRate);
    var d = noiseBuffer.getChannelData(0);
    for (var i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
  }

  function unlock() {
    if (!AC) return;
    if (!ctx) { build(new AC()); }
    if (ctx.state === 'suspended' && !document.hidden) ctx.resume();
    if (settings.music) Music.play(document.body.dataset.music, +document.body.dataset.zone || 1);
  }
  ['pointerdown', 'keydown', 'touchend'].forEach(function (ev) {
    document.addEventListener(ev, unlock, { capture: true, passive: true });
  });
  document.addEventListener('visibilitychange', function () {
    if (!ctx) return;
    if (document.hidden) ctx.suspend(); else ctx.resume();
  });

  // ── Synthesis helpers ───────────────────────────────────────────────────────
  // Envelopes never ramp to 0 (exponential ramps can't), they ramp to 0.0001.
  // Initial values are set explicitly: a GainNode is 1.0 until its first event, and when a
  // start time falls between samples the source can begin one frame early — a full-volume click.
  function tone(freq, t, dur, o) {
    o = o || {};
    var osc = ctx.createOscillator(), g = ctx.createGain(), out = osc;
    osc.type = o.type || 'sine';
    g.gain.value = 0;
    osc.frequency.value = freq;
    osc.frequency.setValueAtTime(freq, t);
    if (o.to) osc.frequency.exponentialRampToValueAtTime(o.to, t + dur);
    if (o.detune) osc.detune.value = o.detune;
    if (o.lp) {
      var f = ctx.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = o.lp;
      osc.connect(f); out = f;
    }
    var peak = o.gain == null ? 0.2 : o.gain, a = o.attack || 0.005, rel = o.release == null ? dur : o.release;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(peak, t + a);
    if (o.hold) g.gain.setValueAtTime(peak, t + Math.max(a, dur - rel));
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    out.connect(g); g.connect(o.dest || sfxBus);
    osc.start(t); osc.stop(t + dur + 0.05);
  }

  function noise(t, dur, o) {
    o = o || {};
    var src = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain();
    src.buffer = noiseBuffer;
    f.type = o.filter || 'bandpass';
    g.gain.value = 0;
    f.frequency.value = o.freq || 1000;
    f.frequency.setValueAtTime(o.freq || 1000, t);
    if (o.to) f.frequency.exponentialRampToValueAtTime(o.to, t + dur);
    f.Q.value = o.q || 1;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(o.gain == null ? 0.2 : o.gain, t + (o.attack || 0.004));
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    src.connect(f); f.connect(g); g.connect(o.dest || sfxBus);
    src.start(t, Math.random() * 0.4); src.stop(t + dur + 0.05);
  }

  function notes(list, t, step, dur, o) {
    list.forEach(function (f, i) { tone(f, t + i * step, dur, o); });
  }

  // ── Sound effects ───────────────────────────────────────────────────────────
  var SFX = {
    click:   function (t) { tone(1400, t, 0.035, { type: 'square', gain: 0.07, lp: 3000 }); },
    step:    function (t) { noise(t, 0.07, { filter: 'lowpass', freq: 500, gain: 0.25 });
                            noise(t + 0.2, 0.07, { filter: 'lowpass', freq: 450, gain: 0.2 }); },
    slash:   function (t) { noise(t, 0.2, { freq: 2600, to: 500, q: 0.9, gain: 0.45 });
                            tone(120, t + 0.06, 0.16, { type: 'triangle', to: 55, gain: 0.35 }); },
    spell:   function (t) { tone(380, t, 0.45, { to: 1150, gain: 0.16 });
                            tone(570, t + 0.05, 0.4, { type: 'triangle', to: 1700, gain: 0.07 });
                            noise(t + 0.1, 0.35, { filter: 'highpass', freq: 6000, gain: 0.05 }); },
    shield:  function (t) { noise(t, 0.08, { freq: 3200, q: 4, gain: 0.25 });
                            tone(240, t, 0.3, { type: 'square', lp: 1100, gain: 0.1 });
                            tone(360, t, 0.3, { type: 'square', lp: 1100, gain: 0.06 }); },
    whoosh:  function (t) { noise(t, 0.4, { freq: 300, to: 3200, q: 1.4, gain: 0.35, attack: 0.08 }); },
    potion:  function (t) { for (var i = 0; i < 4; i++) tone(420 + i * 140, t + i * 0.07, 0.07, { to: 800 + i * 180, gain: 0.12 }); },
    crit:    function (t) { noise(t, 0.16, { freq: 5200, q: 0.8, gain: 0.35 });
                            tone(1760, t, 0.14, { type: 'square', lp: 4200, gain: 0.12 });
                            tone(95, t, 0.3, { to: 40, gain: 0.35 }); },
    hurt:    function (t) { noise(t, 0.22, { filter: 'lowpass', freq: 650, gain: 0.35 });
                            tone(85, t, 0.28, { to: 40, gain: 0.35 });
                            buzz(35); },
    heal:    function (t) { notes([523, 659, 784, 1047], t, 0.08, 0.5, { type: 'triangle', gain: 0.1 }); },
    poison:  function (t) { tone(210, t, 0.45, { type: 'sawtooth', lp: 520, to: 120, gain: 0.12 });
                            tone(214, t, 0.45, { type: 'sawtooth', lp: 520, to: 124, gain: 0.1 }); },
    stun:    function (t) { [900, 700, 900, 700].forEach(function (f, i) { tone(f, t + i * 0.06, 0.05, { type: 'square', lp: 2500, gain: 0.05 }); }); },
    buff:    function (t) { tone(660, t, 0.35, { to: 990, gain: 0.1 }); tone(880, t + 0.06, 0.35, { to: 1320, gain: 0.07 }); },
    levelup: function (t) { notes([523, 659, 784, 1047, 1319], t, 0.09, 0.35, { type: 'triangle', gain: 0.14 });
                            tone(1047, t + 0.45, 0.8, { type: 'triangle', gain: 0.1 }); },
    victory: function (t) { notes([392, 523, 659], t, 0.11, 0.2, { type: 'square', lp: 2200, gain: 0.09 });
                            [523, 659, 784, 1047].forEach(function (f) { tone(f, t + 0.36, 1.0, { type: 'triangle', gain: 0.1, hold: true, release: 0.5 }); }); },
    death:   function (t) { notes([392, 349, 311, 262, 196], t, 0.24, 0.45, { type: 'triangle', gain: 0.14 });
                            tone(98, t + 1.2, 1.6, { type: 'sawtooth', lp: 400, gain: 0.12 }); },
    loot:    function (t) { notes([1568, 2093, 2637], t, 0.06, 0.25, { gain: 0.07 }); },
    coins:   function (t) { tone(1975, t, 0.08, { type: 'square', lp: 6000, gain: 0.05 });
                            tone(2637, t + 0.07, 0.3, { type: 'square', lp: 6000, gain: 0.05 }); },
    quest:   function (t) { [523, 659, 784].forEach(function (f) { tone(f, t, 0.5, { type: 'triangle', gain: 0.09 }); });
                            [659, 784, 1047].forEach(function (f) { tone(f, t + 0.25, 0.8, { type: 'triangle', gain: 0.09 }); }); },
    lore:    function (t) { tone(220, t, 2.2, { gain: 0.16 }); tone(220 * 2.76, t, 1.2, { gain: 0.04 });
                            tone(330, t + 0.4, 1.8, { gain: 0.08 }); },
    fail:    function (t) { tone(160, t, 0.2, { type: 'square', lp: 600, gain: 0.1 });
                            tone(120, t + 0.14, 0.3, { type: 'square', lp: 500, gain: 0.1 }); },
    pick:    function (t) { noise(t, 0.03, { freq: 4000, q: 2, gain: 0.3 });
                            tone(2300, t, 0.25, { type: 'triangle', gain: 0.1 }); tone(3480, t, 0.15, { gain: 0.04 }); },
    chop:    function (t) { noise(t, 0.09, { filter: 'lowpass', freq: 900, gain: 0.5 });
                            tone(190, t, 0.12, { type: 'triangle', to: 90, gain: 0.3 }); },
    splash:  function (t) { noise(t, 0.45, { freq: 1300, to: 380, q: 0.7, gain: 0.35 });
                            tone(600, t + 0.15, 0.08, { to: 1000, gain: 0.06 }); },
    rustle:  function (t) { noise(t, 0.2, { filter: 'highpass', freq: 3200, gain: 0.12 });
                            noise(t + 0.15, 0.2, { filter: 'highpass', freq: 2800, gain: 0.1 }); },
    anvil:   function (t) { noise(t, 0.03, { freq: 5000, q: 1, gain: 0.35 });
                            tone(1100, t, 0.9, { type: 'triangle', gain: 0.12 });
                            tone(1663, t, 0.6, { gain: 0.06 }); tone(2490, t, 0.4, { gain: 0.04 }); },
    sizzle:  function (t) { noise(t, 0.7, { filter: 'highpass', freq: 5000, gain: 0.08, attack: 0.05 }); },
    bubbles: function (t) { for (var i = 0; i < 6; i++) tone(300 + Math.random() * 500, t + i * 0.07, 0.06, { to: 900 + Math.random() * 600, gain: 0.07 }); },
    discover:function (t) { notes([523, 740, 988], t, 0.15, 0.9, { gain: 0.09 });
                            noise(t, 0.8, { filter: 'highpass', freq: 7000, gain: 0.03, attack: 0.3 }); },
    rest:    function (t) { [392, 494, 587].forEach(function (f, i) { tone(f, t + i * 0.12, 1.4, { type: 'triangle', gain: 0.07, attack: 0.1 }); }); },
    clank:   function (t) { noise(t, 0.06, { freq: 2200, q: 3, gain: 0.3 });
                            tone(320, t, 0.12, { type: 'square', lp: 1200, gain: 0.07 }); }
  };

  function sfx(name, delay) {
    if (!ctx || !settings.sfx || !SFX[name] || ctx.state !== 'running') return;
    SFX[name](ctx.currentTime + 0.01 + (delay || 0));
  }

  function buzz(ms) {   // Android haptics; ignored elsewhere
    if (settings.sfx && navigator.vibrate) { try { navigator.vibrate(ms); } catch (e) {} }
  }

  // The sound of pressing a button, by its action value.
  function actionSound(v) {
    if (v === 'attack') return 'slash';
    if (v === 'defend') return 'shield';
    if (v === 'flee' || v.indexOf('travel_') === 0) return 'whoosh';
    if (v.indexOf('ability_') === 0) return 'spell';
    if (v.indexOf('item_') === 0 || v.indexOf('use_') === 0) return 'potion';
    if (v === 'explore' || v.indexOf('choose_') === 0) return 'step';
    if (v === 'gather_Mining') return 'pick';
    if (v === 'gather_Woodcutting') return 'chop';
    if (v === 'gather_Fishing') return 'splash';
    if (v === 'gather_Herbalism') return 'rustle';
    if (v === 'ws_forge' || v.indexOf('craft_Smithing') === 0 || v.indexOf('upgrade_') === 0 || v.indexOf('temper_') === 0) return 'anvil';
    if (v.indexOf('craft_Cooking') === 0) return 'sizzle';
    if (v === 'alc_mix' || v.indexOf('alc_brew_') === 0) return 'bubbles';
    if (v.indexOf('craft_') === 0) return 'chop';
    if (v.indexOf('buy_') === 0 || v.indexOf('sell_') === 0) return 'coins';
    if (v.indexOf('equip_') === 0) return 'clank';
    if (v === 'full_rest' || v === 'nap') return 'rest';
    return 'click';
  }

  // Result sounds for new messages, most important first; at most three play.
  var RESULT_SOUNDS = [
    ['victory', 'victory'], ['levelup', 'levelup'], ['quest', 'quest'], ['crit', 'crit'],
    ['enemy', 'hurt'], ['stun', 'stun'], ['poison', 'poison'], ['heal', 'heal'], ['loot', 'loot'],
    ['gold', 'coins'], ['buff', 'buff'], ['lore', 'lore'], ['danger', 'fail']
  ];

  // ── Music ───────────────────────────────────────────────────────────────────
  var SCALES = {
    ionian:   [0, 2, 4, 5, 7, 9, 11], lydian: [0, 2, 4, 6, 7, 9, 11], dorian: [0, 2, 3, 5, 7, 9, 10],
    aeolian:  [0, 2, 3, 5, 7, 8, 10], phrygian: [0, 1, 3, 5, 7, 8, 10], harmonic: [0, 2, 3, 5, 7, 8, 11]
  };
  // Zone mood: Starter Village, Dark Forest, Cursed Ruins, Shadow Realm, Dragon's Peak.
  var ZONE_MODE = { 1: ['lydian', 50], 2: ['dorian', 50], 3: ['aeolian', 48], 4: ['phrygian', 47], 5: ['harmonic', 45] };

  function pat(s) { return s.replace(/ /g, '').split('').map(function (c) { return c === '.' ? 0 : c === 'o' ? 2 : 1; }); }

  // Each theme: tempo, key, chord progression (scale degrees, one per bar) and voices.
  function theme(id, zone) {
    var zm = ZONE_MODE[zone] || ZONE_MODE[1];
    switch (id) {
      case 'title': return { id: id, bpm: 66, scale: 'aeolian', root: 45, prog: [0, 5, 3, 4],
        pad: 0.05, bass: pat('x... .... .... ....'), lead: { density: 0.35, every: 4, type: 'sine', gain: 0.07, oct: 2 } };
      case 'town': return { id: id + zone, bpm: 84, scale: zm[0], root: zm[1], prog: [0, 3, 4, 0],
        pad: 0.04, bass: pat('x... .... x... ....'), arp: pat('x.x. x.x. x.x. x.x.'), arpGain: 0.03,
        lead: { density: 0.4, every: 2, type: 'triangle', gain: 0.06, oct: 2 } };
      case 'explore': return { id: id + zone, bpm: 100, scale: zm[0], root: zm[1], prog: [0, 5, 3, 4],
        pad: 0.03, bass: pat('x.x. x.x. x.x. x.o.'), hat: pat('..x. ..x. ..x. ..x.'),
        lead: { density: 0.5, every: 2, type: 'triangle', gain: 0.06, oct: 2 } };
      case 'combat': return { id: id + zone, bpm: 132, scale: zone === 1 ? 'dorian' : zm[0] === 'lydian' ? 'aeolian' : zm[0], root: zm[1],
        prog: [0, 0, 5, 6], bassType: 'sawtooth', bass: pat('x.xo x.xo x.xo x.xx'),
        kick: pat('x... .... x... ....'), snare: pat('.... x... .... x...'), hat: pat('x.x. x.x. x.x. x.x.'),
        lead: { density: 0.45, every: 2, type: 'square', gain: 0.035, oct: 2 } };
      case 'boss': return { id: id + zone, bpm: 144, scale: 'harmonic', root: zm[1] - 2, prog: [0, 5, 1, 4],
        pad: 0.03, bassType: 'sawtooth', bass: pat('xxox xxox xxox xoxo'),
        kick: pat('x..x ..x. x..x ..x.'), snare: pat('.... x... .... x..x'), hat: pat('xxxx xxxx xxxx xxxx'),
        lead: { density: 0.5, every: 2, type: 'square', gain: 0.035, oct: 2 } };
      case 'final': return { id: id, bpm: 152, scale: 'phrygian', root: 40, prog: [0, 1, 0, 6],
        pad: 0.04, bassType: 'sawtooth', bass: pat('xxxx xxxo xxxx xoxo'),
        kick: pat('x.xx ..x. x.xx ..x.'), snare: pat('.... x... .... x.xx'), hat: pat('xxxx xxxx xxxx xxxx'),
        lead: { density: 0.55, every: 1, type: 'sawtooth', gain: 0.025, oct: 2 } };
      case 'ending': return { id: id, bpm: 76, scale: 'ionian', root: 48, prog: [0, 4, 5, 3],
        pad: 0.05, bass: pat('x... .... x... ....'), arp: pat('x.x. x.x. x.x. x.x.'), arpGain: 0.035,
        lead: { density: 0.45, every: 2, type: 'triangle', gain: 0.07, oct: 2 } };
    }
    return null;
  }

  function mtof(m) { return 440 * Math.pow(2, (m - 69) / 12); }
  function degreeToMidi(th, deg) {
    var sc = SCALES[th.scale], o = Math.floor(deg / 7), i = ((deg % 7) + 7) % 7;
    return th.root + 12 * o + sc[i];
  }
  function rng(seed) {   // mulberry32: same seed, same phrase, so themes loop recognisably
    return function () {
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      var t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  function hash(s) { var h = 7; for (var i = 0; i < s.length; i++) h = h * 31 + s.charCodeAt(i) | 0; return h; }

  var Music = {
    current: null,   // {theme, gain, step, nextTime, lastDeg}
    timer: null,
    wanted: null,

    play: function (id, zone) {
      this.wanted = [id, zone];
      if (!ctx || !settings.music) return;
      var th = theme(id, zone);
      if (this.current && th && this.current.theme.id === th.id) return;   // same theme keeps playing
      this.stop(1.2);
      if (!th) return;
      var g = ctx.createGain(), t = ctx.currentTime;
      g.gain.value = 0;
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(1, t + 1.5);
      g.connect(musicBus);
      this.current = { theme: th, gain: g, step: 0, nextTime: t + 0.1, lastDeg: 7 };
      if (!this.timer) this.timer = setInterval(function () { Music.tick(); }, 50);
    },

    stop: function (fade) {
      var cur = this.current;
      this.current = null;
      if (cur && ctx) {
        var t = ctx.currentTime;
        cur.gain.gain.cancelScheduledValues(t);
        cur.gain.gain.setValueAtTime(Math.max(cur.gain.gain.value, 0.0001), t);
        cur.gain.gain.exponentialRampToValueAtTime(0.0001, t + (fade || 0.3));
        setTimeout(function () { cur.gain.disconnect(); }, ((fade || 0.3) + 0.5) * 1000);
      }
      if (!this.current && this.timer) { clearInterval(this.timer); this.timer = null; }
    },

    tick: function () {
      var cur = this.current;
      if (!cur || !ctx || ctx.state !== 'running') return;
      if (cur.nextTime < ctx.currentTime) cur.nextTime = ctx.currentTime + 0.05;   // timers were throttled
      while (cur.nextTime < ctx.currentTime + 0.25) {
        this.scheduleStep(cur, cur.step, cur.nextTime);
        cur.nextTime += 60 / cur.theme.bpm / 4;
        cur.step++;
      }
    },

    scheduleStep: function (cur, step, t) {
      var th = cur.theme, s = step % 16, bar = Math.floor(step / 16);
      var spb = 60 / th.bpm / 4, barLen = spb * 16, out = cur.gain;
      var chord = th.prog[bar % th.prog.length];
      var tones = [chord, chord + 2, chord + 4];
      if (s === 0 && th.pad) {
        tones.forEach(function (d) {
          var f = mtof(degreeToMidi(th, d) + 12);
          tone(f, t, barLen, { type: 'sawtooth', lp: 900, gain: th.pad, attack: 0.4, hold: true, release: 0.5, detune: -6, dest: out });
          tone(f, t, barLen, { type: 'sawtooth', lp: 900, gain: th.pad, attack: 0.4, hold: true, release: 0.5, detune: 6, dest: out });
        });
      }
      if (th.bass && th.bass[s]) {
        var bm = degreeToMidi(th, chord) - 12 + (th.bass[s] === 2 ? 12 : 0), gap = 1;
        while (gap < 16 && !th.bass[(s + gap) % 16]) gap++;   // end before the next note: no stacking
        tone(mtof(bm), t, spb * Math.min(1.8, gap * 0.9), { type: th.bassType || 'triangle', lp: th.bassType ? 500 : 0, gain: th.bassType ? 0.1 : 0.16, dest: out });
      }
      if (th.arp && th.arp[s]) {
        var ad = tones[(s / 2) % 3 | 0] + (s >= 8 ? 7 : 0);
        tone(mtof(degreeToMidi(th, ad) + 12), t, spb * 1.5, { gain: th.arpGain, dest: out });
      }
      var L = th.lead;
      if (L && s % L.every === 0) {
        var r = rng(hash(th.id) + (bar % 8) * 97 + s);
        if (r() < L.density) {
          var d = r() < 0.6 ? tones[r() * 3 | 0] + 7 : cur.lastDeg + (r() < 0.5 ? -1 : 1);
          d = Math.max(5, Math.min(13, d));
          cur.lastDeg = d;
          var len = spb * L.every * (r() < 0.3 ? 2 : 1);
          tone(mtof(degreeToMidi(th, d) + 12 * (L.oct - 1)), t, len,
               { type: L.type, lp: L.type === 'sine' ? 0 : 2400, gain: L.gain, attack: 0.02, dest: out });
        }
      }
      if (th.kick && th.kick[s]) tone(120, t, 0.16, { to: 45, gain: 0.3, dest: out });
      if (th.snare && th.snare[s]) {
        noise(t, 0.13, { freq: 1800, q: 0.8, gain: 0.12, dest: out });
        tone(190, t, 0.08, { type: 'triangle', gain: 0.06, dest: out });
      }
      if (th.hat && th.hat[s]) noise(t, 0.03, { filter: 'highpass', freq: 7500, gain: 0.04, dest: out });
    }
  };

  // ── Screen updates ──────────────────────────────────────────────────────────
  function messageTexts() {
    return Array.prototype.map.call(document.querySelectorAll('.screen .msg'), function (m) {
      return { text: m.textContent, kinds: m.className };
    });
  }

  // Messages that weren't on the previous screen. The combat log keeps growing during a
  // fight (and the victory screen shows all of it), so only the new tail counts.
  function newMessages(before, after) {
    if (before.length > after.length) return after;
    for (var i = 0; i < before.length; i++) if (before[i].text !== after[i].text) return after;
    return after.slice(before.length);
  }

  function onScreen(prev) {
    var body = document.body;
    if (settings.music) Music.play(body.dataset.music, +body.dataset.zone || 1);
    if (body.dataset.music === 'none') Music.stop(0.8);
    if (!prev) return;                                   // first page load: no result sounds
    var fresh = newMessages(prev.msgs, messageTexts());
    var kinds = fresh.map(function (m) { return m.kinds; }).join(' ');
    if (body.dataset.screen === 'game_over' && prev.screen !== 'game_over') { sfx('death', 0.2); return; }
    if (body.dataset.screen === 'node' && prev.screen !== 'node') sfx('discover', 0.05);
    var played = 0;
    RESULT_SOUNDS.forEach(function (rs) {
      if (played < 3 && kinds.indexOf('msg-' + rs[0]) !== -1) { sfx(rs[1], 0.12 + played * 0.18); played++; }
    });
    if (kinds.indexOf('msg-crit') !== -1) {
      var ec = document.querySelector('.enemy-card'); if (ec) ec.classList.add('crit-flash');
      buzz(60);
    }
    if (kinds.indexOf('msg-enemy') !== -1) {
      var bt = document.querySelector('.bar-track'); if (bt) bt.classList.add('damaged');
    }
    if (kinds.indexOf('msg-levelup') !== -1) {
      var sb = document.querySelector('.status-bar'); if (sb) sb.classList.add('levelup');
    }
  }

  var busy = false, lastButton = null;

  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('button');
    if (!btn || btn.closest('.sound-panel')) return;
    lastButton = btn;
    if (btn.form) sfx(actionSound(btn.value || ''));
  });

  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!window.fetch || !window.DOMParser || (form.getAttribute('method') || '').toLowerCase() !== 'post') return;
    e.preventDefault();
    if (busy) return;                                    // ignore double taps while a turn is in flight
    busy = true;
    var data = new FormData(form);
    var submitter = e.submitter || (lastButton && lastButton.form === form ? lastButton : null);
    if (submitter && submitter.name) data.append(submitter.name, submitter.value);
    var prev = { screen: document.body.dataset.screen, msgs: messageTexts() };
    // getAttribute, not form.action: the buttons are named "action", which shadows the property.
    fetch(form.getAttribute('action') || window.location.href, { method: 'POST', body: data, credentials: 'same-origin' })
      .then(function (res) { if (!res.ok) throw new Error(res.status); return res.text(); })
      .then(function (html) {
        var doc = new DOMParser().parseFromString(html, 'text/html');
        var next = doc.querySelector('.screen');
        if (!next) throw new Error('no screen');
        document.querySelector('.screen').replaceWith(document.adoptNode(next));
        document.body.className = doc.body.className;
        ['screen', 'music', 'zone'].forEach(function (k) { document.body.dataset[k] = doc.body.dataset[k] || ''; });
        window.scrollTo(0, 0);
        onScreen(prev);
      })
      .catch(function () { window.location.reload(); })  // fall back to a normal page load
      .then(function () { busy = false; });
  });

  // ── Sound settings button ───────────────────────────────────────────────────
  function buildControls() {
    var wrap = document.createElement('div');
    wrap.className = 'sound-panel';
    wrap.innerHTML =
      '<div class="sound-menu" hidden>' +
      '<button type="button" data-toggle="music"></button>' +
      '<button type="button" data-toggle="sfx"></button>' +
      '</div>' +
      '<button type="button" class="sound-fab" aria-label="Sound settings"></button>';
    document.body.appendChild(wrap);
    var menu = wrap.querySelector('.sound-menu'), fab = wrap.querySelector('.sound-fab');
    function render() {
      wrap.querySelector('[data-toggle=music]').textContent = (settings.music ? '🎵 Music: on' : '🎵 Music: off');
      wrap.querySelector('[data-toggle=sfx]').textContent = (settings.sfx ? '🔊 Sound: on' : '🔈 Sound: off');
      fab.textContent = settings.music || settings.sfx ? '🔊' : '🔇';
    }
    fab.addEventListener('click', function () { menu.hidden = !menu.hidden; });
    wrap.addEventListener('click', function (e) {
      var key = e.target.getAttribute && e.target.getAttribute('data-toggle');
      if (!key) return;
      settings[key] = !settings[key];
      saveSettings();
      if (ctx) {
        var bus = key === 'music' ? musicBus : sfxBus, lvl = key === 'music' ? MUSIC_LEVEL : SFX_LEVEL;
        bus.gain.setTargetAtTime(settings[key] ? lvl : 0, ctx.currentTime, 0.1);
      }
      if (key === 'music') {
        if (settings.music) Music.play(document.body.dataset.music, +document.body.dataset.zone || 1);
        else Music.stop(0.4);
      }
      render();
    });
    document.addEventListener('click', function (e) {
      if (!menu.hidden && !wrap.contains(e.target)) menu.hidden = true;
    });
    render();
  }

  function init() {
    buildControls();
    onScreen(null);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();

  // Test hook: render sounds/music into an OfflineAudioContext (tools / browser tests only).
  window.__rpgAudio = {
    sounds: Object.keys(SFX),
    themes: ['title', 'town', 'explore', 'combat', 'boss', 'final', 'ending'],
    status: function () { return { ctx: ctx && ctx.state, theme: Music.current && Music.current.theme.id, settings: settings }; },
    actionSound: actionSound,
    newMessages: newMessages,
    renderSound: function (offline, name) { build(offline); SFX[name](0.05); return offline.startRendering(); },
    renderTheme: function (offline, id, zone, seconds) {
      build(offline);
      var cur = { theme: theme(id, zone), gain: musicBus, step: 0, nextTime: 0.05, lastDeg: 7 };
      while (cur.nextTime < seconds - 1) { Music.scheduleStep(cur, cur.step, cur.nextTime); cur.nextTime += 60 / cur.theme.bpm / 4; cur.step++; }
      return offline.startRendering();
    }
  };
})();
