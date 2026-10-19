/*
 * Editor de la tarjeta del comercio (color, premio, logo y portada) con vista previa.
 * Lo usan /alta y /pos. Cada página define los colores del editor con las variables --ed-*.
 *
 *   const editor = SelloCardEditor.create(contenedor, { name, brand_color, reward_text, logo_url, hero_url });
 *   editor.setName("Café Roma");
 *   editor.getValues();  // { brand_color, reward_text, logo, hero, remove_logo, remove_hero }
 */
(function () {
  const DEFAULT_COLOR = "#1E3A8A";
  const MAX_REWARD = 60;
  const PRESETS = ["#1E3A8A", "#0F766E", "#15803D", "#B45309", "#B91C1C", "#9D174D", "#6D28D9", "#111827"];

  // Tamaños recomendados por Google Wallet
  const IMAGE_SPECS = {
    logo: { width: 660, height: 660, type: "image/png" },
    hero: { width: 1032, height: 336, type: "image/jpeg", quality: 0.85 },
  };

  const STYLE = `
    .ce { display: grid; gap: 18px; }
    .ce-field label.ce-label { display: block; font-size: 13px; font-weight: 600; color: var(--ed-text); margin-bottom: 6px; }
    .ce-hint { font-size: 12px; color: var(--ed-muted); margin-top: 6px; }
    .ce-colors { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
    .ce-swatch { width: 30px; height: 30px; border-radius: 50%; border: 2px solid transparent; cursor: pointer; padding: 0; outline-offset: 2px; }
    .ce-swatch[aria-pressed="true"] { border-color: var(--ed-text); box-shadow: 0 0 0 2px var(--ed-bg) inset; }
    .ce-custom { display: flex; align-items: center; gap: 6px; margin-left: 4px; }
    .ce-custom input[type=color] { width: 34px; height: 34px; border: none; padding: 0; background: none; cursor: pointer; }
    .ce-custom span { font-size: 13px; color: var(--ed-muted); font-family: ui-monospace, Menlo, monospace; }
    .ce input[type=text] { width: 100%; padding: 11px; border: 1px solid var(--ed-border); background: var(--ed-input-bg); color: var(--ed-text); border-radius: 8px; font-size: 15px; box-sizing: border-box; outline: none; }
    .ce input[type=text]:focus { border-color: #2563eb; }
    .ce-upload { display: flex; align-items: center; gap: 12px; }
    .ce-thumb { width: 52px; height: 52px; border-radius: 10px; border: 1px dashed var(--ed-border); background: var(--ed-input-bg) center/cover no-repeat; flex-shrink: 0; }
    .ce-thumb.round { border-radius: 50%; }
    .ce-thumb.wide { width: 96px; height: 32px; border-radius: 6px; }
    .ce-btn { font: inherit; font-size: 13px; font-weight: 600; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--ed-border); background: transparent; color: var(--ed-text); cursor: pointer; }
    .ce-btn.link { border: none; padding: 8px 4px; color: var(--ed-muted); }
    .ce-error { color: #dc2626; font-size: 13px; margin-top: 6px; }

    .ce-preview-title { font-size: 12px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--ed-muted); margin-bottom: 8px; }
    .ce-card { border-radius: 18px; overflow: hidden; box-shadow: 0 10px 24px rgba(0,0,0,.18); font-family: Roboto, -apple-system, "Segoe UI", sans-serif; max-width: 340px; }
    .ce-card-body { padding: 16px 18px 18px; }
    .ce-card-top { display: flex; align-items: center; gap: 10px; font-size: 14px; font-weight: 500; }
    .ce-card-logo { width: 34px; height: 34px; border-radius: 50%; background: rgba(255,255,255,.25) center/cover no-repeat; flex-shrink: 0; display: grid; place-items: center; font-weight: 700; font-size: 15px; }
    .ce-card-header { font-size: 22px; font-weight: 500; margin: 2px 0 0; }
    .ce-card-sub { font-size: 12px; opacity: .8; margin-top: 18px; }
    .ce-card-modules { display: flex; gap: 22px; margin: 16px 0; }
    .ce-card-modules div { min-width: 0; }
    .ce-card-modules small { display: block; font-size: 11px; opacity: .75; text-transform: uppercase; letter-spacing: .04em; }
    .ce-card-modules strong { display: block; font-size: 14px; font-weight: 500; overflow-wrap: anywhere; }
    .ce-card-qr { background: #fff; border-radius: 10px; width: 116px; height: 116px; margin: 0 auto; display: grid; place-items: center; }
    .ce-card-qr div { width: 88px; height: 88px; background:
      linear-gradient(90deg, #111 50%, transparent 0) 0 0/16px 16px,
      linear-gradient(#111 50%, transparent 0) 0 0/16px 16px; opacity: .85; border-radius: 2px; }
    .ce-card-hero { height: 0; padding-bottom: 32.55%; background: center/cover no-repeat; }
  `;

  function injectStyle() {
    if (document.getElementById("card-editor-style")) return;
    const style = document.createElement("style");
    style.id = "card-editor-style";
    style.textContent = STYLE;
    document.head.appendChild(style);
  }

  // Texto blanco o negro según el fondo, como hace Google Wallet
  function textColorFor(hex) {
    const n = parseInt(hex.slice(1), 16);
    const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map(v => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.4 ? "#1f1f1f" : "#ffffff";
  }

  // Recorta la imagen al centro con la proporción pedida y la achica al tamaño recomendado
  function processImage(file, kind) {
    const spec = IMAGE_SPECS[kind];
    return new Promise((resolve, reject) => {
      if (!/^image\/(png|jpeg)$/.test(file.type)) {
        reject(new Error("La imagen tiene que ser PNG o JPG"));
        return;
      }
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        URL.revokeObjectURL(url);
        const targetRatio = spec.width / spec.height;
        let sw = img.naturalWidth, sh = img.naturalHeight;
        if (sw / sh > targetRatio) sw = sh * targetRatio; else sh = sw / targetRatio;
        const sx = (img.naturalWidth - sw) / 2, sy = (img.naturalHeight - sh) / 2;

        const canvas = document.createElement("canvas");
        canvas.width = spec.width;
        canvas.height = spec.height;
        const ctx = canvas.getContext("2d");
        if (spec.type === "image/jpeg") {
          ctx.fillStyle = "#ffffff";
          ctx.fillRect(0, 0, canvas.width, canvas.height);
        }
        ctx.imageSmoothingQuality = "high";
        ctx.drawImage(img, sx, sy, sw, sh, 0, 0, spec.width, spec.height);
        resolve(canvas.toDataURL(spec.type, spec.quality));
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error("No se pudo leer la imagen"));
      };
      img.src = url;
    });
  }

  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => {
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else node.setAttribute(k, v);
    });
    children.forEach(c => node.appendChild(c));
    return node;
  }

  function create(container, initial = {}) {
    injectStyle();

    const state = {
      name: initial.name || "Tu comercio",
      color: (initial.brand_color || DEFAULT_COLOR).toUpperCase(),
      reward: initial.reward_text || "",
      images: {
        logo: { preview: initial.logo_url || null, newData: null, removed: false },
        hero: { preview: initial.hero_url || null, newData: null, removed: false },
      },
    };

    const root = el("div", { class: "ce" });

    // --- Color ---
    const colorField = el("div", { class: "ce-field" });
    colorField.appendChild(el("label", { class: "ce-label", text: "Color de la tarjeta" }));
    const colors = el("div", { class: "ce-colors", role: "group", "aria-label": "Colores sugeridos" });
    const swatches = PRESETS.map(hex => {
      const b = el("button", { type: "button", class: "ce-swatch", "aria-label": `Color ${hex}`, "aria-pressed": "false" });
      b.style.background = hex;
      b.addEventListener("click", () => setColor(hex));
      colors.appendChild(b);
      return b;
    });
    const picker = el("input", { type: "color", "aria-label": "Elegir otro color" });
    const hexLabel = el("span");
    picker.addEventListener("input", () => setColor(picker.value));
    colors.appendChild(el("div", { class: "ce-custom" }, [picker, hexLabel]));
    colorField.appendChild(colors);
    colorField.appendChild(el("div", { class: "ce-hint", text: "El texto de la tarjeta se pone blanco o negro solo, para que se lea bien." }));

    // --- Premio ---
    const rewardField = el("div", { class: "ce-field" });
    const rewardId = "ce-reward-" + Math.random().toString(36).slice(2, 8);
    rewardField.appendChild(el("label", { class: "ce-label", for: rewardId, text: "Premio de tu programa (opcional)" }));
    const rewardInput = el("input", { type: "text", id: rewardId, maxlength: String(MAX_REWARD), placeholder: "Ej: Juntá 100 puntos y llevate un café" });
    rewardInput.value = state.reward;
    const rewardHint = el("div", { class: "ce-hint" });
    rewardInput.addEventListener("input", () => { state.reward = rewardInput.value; render(); });
    rewardField.appendChild(rewardInput);
    rewardField.appendChild(rewardHint);

    // --- Imágenes ---
    function imageField(kind, label, hint, thumbClass) {
      const field = el("div", { class: "ce-field" });
      const inputId = `ce-${kind}-` + Math.random().toString(36).slice(2, 8);
      field.appendChild(el("label", { class: "ce-label", for: inputId, text: label }));
      const thumb = el("div", { class: "ce-thumb " + thumbClass });
      const input = el("input", { type: "file", id: inputId, accept: "image/png,image/jpeg", hidden: "" });
      const choose = el("button", { type: "button", class: "ce-btn", text: "Elegir imagen" });
      const remove = el("button", { type: "button", class: "ce-btn link", text: "Quitar" });
      const error = el("div", { class: "ce-error" });
      choose.addEventListener("click", () => input.click());
      input.addEventListener("change", async () => {
        const file = input.files[0];
        input.value = "";
        if (!file) return;
        error.textContent = "";
        try {
          const data = await processImage(file, kind);
          Object.assign(state.images[kind], { preview: data, newData: data, removed: false });
          render();
        } catch (e) {
          error.textContent = e.message;
        }
      });
      remove.addEventListener("click", () => {
        Object.assign(state.images[kind], { preview: null, newData: null, removed: true });
        render();
      });
      field.appendChild(el("div", { class: "ce-upload" }, [thumb, choose, remove, input]));
      field.appendChild(el("div", { class: "ce-hint", text: hint }));
      field.appendChild(error);
      state.images[kind].thumb = thumb;
      state.images[kind].removeBtn = remove;
      return field;
    }

    const logoField = imageField("logo", "Logo (opcional)", "Se muestra en un círculo. Usá una imagen cuadrada con el logo centrado.", "round");
    const heroField = imageField("hero", "Imagen de portada (opcional)", "Un banner ancho abajo de la tarjeta, por ejemplo una foto del local. Se recorta a 1032 × 336.", "wide");

    // --- Vista previa ---
    const previewWrap = el("div");
    previewWrap.appendChild(el("div", { class: "ce-preview-title", text: "Así se ve en Google Wallet" }));
    const card = el("div", { class: "ce-card", "aria-hidden": "true" });
    previewWrap.appendChild(card);

    [colorField, rewardField, logoField, heroField, previewWrap].forEach(n => root.appendChild(n));
    container.innerHTML = "";
    container.appendChild(root);

    function setColor(hex) {
      state.color = hex.toUpperCase();
      render();
    }

    function render() {
      swatches.forEach((b, i) => b.setAttribute("aria-pressed", String(PRESETS[i] === state.color)));
      picker.value = state.color.toLowerCase();
      hexLabel.textContent = state.color;
      rewardHint.textContent = `${state.reward.length}/${MAX_REWARD} caracteres`;

      ["logo", "hero"].forEach(kind => {
        const img = state.images[kind];
        img.thumb.style.backgroundImage = img.preview ? `url("${img.preview}")` : "";
        img.removeBtn.hidden = !img.preview;
      });

      const fg = textColorFor(state.color);
      const logo = state.images.logo.preview;
      const hero = state.images.hero.preview;
      card.style.background = state.color;
      card.style.color = fg;
      card.innerHTML = "";

      const logoEl = el("div", { class: "ce-card-logo" });
      if (logo) logoEl.style.backgroundImage = `url("${logo}")`;
      else logoEl.textContent = (state.name.trim()[0] || "S").toUpperCase();

      const modules = el("div", { class: "ce-card-modules" }, [
        el("div", {}, [el("small", { text: "Puntos" }), el("strong", { text: "120 pts" })]),
      ]);
      if (state.reward.trim()) {
        modules.appendChild(el("div", {}, [el("small", { text: "Premio" }), el("strong", { text: state.reward.trim() })]));
      }

      card.appendChild(el("div", { class: "ce-card-body" }, [
        el("div", { class: "ce-card-top" }, [logoEl, el("span", { text: state.name || "Tu comercio" })]),
        el("div", { class: "ce-card-sub", text: "Cliente" }),
        el("div", { class: "ce-card-header", text: "Ana García" }),
        modules,
        el("div", { class: "ce-card-qr" }, [el("div")]),
      ]));
      if (hero) {
        const heroEl = el("div", { class: "ce-card-hero" });
        heroEl.style.backgroundImage = `url("${hero}")`;
        card.appendChild(heroEl);
      }
    }

    render();

    return {
      setName(name) {
        state.name = name;
        render();
      },
      getValues() {
        return {
          brand_color: state.color,
          reward_text: state.reward.trim(),
          logo: state.images.logo.newData,
          hero: state.images.hero.newData,
          remove_logo: state.images.logo.removed,
          remove_hero: state.images.hero.removed,
        };
      },
    };
  }

  window.SelloCardEditor = { create, textColorFor };
})();
