/* How it works: the six steps of the How it works page as an animated walkthrough.
   The page is complete without this script (every step is plain text); the script reads the day's numbers from
   data-cfg (written by scripts/pages.py at each update), draws posts as dots that flow from the sources, are sorted,
   gather into stories, and then shows the mood gap, the topic gap and what gets published. Plays on its own, one step
   every few seconds, from the moment it comes into view; it stays still for people who turn off motion. */
(() => {
  const root = document.getElementById("how");
  if (!root) return;
  const C = JSON.parse(root.dataset.cfg || "{}");
  const stage = root.querySelector(".how-stage"), ctrl = root.querySelector(".how-ctrl"), barBox = root.querySelector(".how-bar");
  const items = [...root.querySelectorAll(".how-steps li")], buttons = [...ctrl.querySelectorAll("[data-go]")], pp = ctrl.querySelector(".pp");
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  root.classList.add("js");
  stage.hidden = ctrl.hidden = barBox.hidden = false;
  const small = stage.clientWidth < 560;              // phones: a taller stage, so the drawing is not letterboxed
  const YS = small ? 1.6 : 1, W = 800, H = 400 * YS, N = 84, STEP_MS = 7000;
  const X = (x) => (C.rtl ? W - x : x);            // the flow runs in the reading direction
  const Y = (y) => y * YS;
  const bar = barBox.querySelector("i");

  const NS = "http://www.w3.org/2000/svg";
  const mk = (tag, attrs, text) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (text != null) e.textContent = text; return e; };
  const svg = mk("svg", { viewBox: `0 0 ${W} ${H}`, style: "direction:ltr" });
  stage.appendChild(svg);
  let seed = 11;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;

  // the sources down the reading-start side
  const srcY = C.sources.map((_, i) => 48 + i * 61);
  const srcLabels = C.sources.map((t, i) => svg.appendChild(mk("text", { x: X(22), y: Y(srcY[i]) + 5, class: "src", "text-anchor": C.rtl ? "end" : "start" }, t)));
  const label = (x, y, text, cls = "lbl", anchor = "start") => svg.appendChild(mk("text", { x: X(x), y: Y(y), class: cls, "text-anchor": C.rtl ? { start: "end", end: "start" }[anchor] || anchor : anchor, opacity: 0 }, text));
  const lPeople = label(560, 52, C.people), lOutlets = label(560, 236, C.outlets), lAside = label(330, 388, C.setAside);

  // the stories, largest first, as clusters
  const stories = (C.stories && C.stories.length ? C.stories : [{ t: "", s: 1 }]).slice(0, 5);
  const centres = [[470, 175], [265, 270], [655, 285], [270, 105], [660, 100]];
  const total = stories.reduce((a, s) => a + (s.s || 0.01), 0) || 1;
  const clusters = stories.map((s, k) => ({ x: centres[k][0], y: centres[k][1], r: 24 + 62 * Math.sqrt((s.s || 0.01) / total) }));
  const short = (t) => (t.length > 30 ? t.slice(0, 29).replace(/\s+\S*$/, "") + "…" : t);
  const storyLabels = clusters.slice(0, 3).map((c, k) => label(c.x, Math.min(392, c.y + c.r + 18), short(stories[k].t), "story", "middle"));

  // the dots: about a quarter set aside, the rest people or outlets in today's proportion, each in a story
  const share = C.split && C.split[0] + C.split[1] ? C.split[0] / (C.split[0] + C.split[1]) : 0.7;
  const dots = [];
  for (let i = 0; i < N; i++) {
    const drop = rnd() < 0.27, people = rnd() < share;
    let pick = rnd() * total, k = 0;
    while (k < stories.length - 1 && (pick -= stories[k].s || 0.01) > 0) k++;
    const a = rnd() * Math.PI * 2, d = Math.sqrt(rnd()) * clusters[k].r;
    const e = svg.appendChild(mk("circle", { r: small ? 9 : 6, class: "dot", cx: 0, cy: 0 }));
    dots.push({ e, drop, people, k, src: i % C.sources.length, delay: rnd() * 1.4,
                pile: [300 + rnd() * 170, 60 + rnd() * 280], lane: [560 + rnd() * 180, people ? 72 + rnd() * 120 : 256 + rnd() * 100],
                cl: [clusters[k].x + Math.cos(a) * d, clusters[k].y + Math.sin(a) * d], out: [330 + rnd() * 120, 430] });
  }
  const BRASS = "#8A6420", GREY = "#A7ABA3", NEUTRAL = "#6B6559", PALE = "#D9D2C2";
  const place = (d, [x, y], opacity, fill, delay = 0) => {
    d.e.style.transitionDelay = reduce ? "0s" : `${delay}s`;
    d.e.style.transform = `translate(${X(x)}px, ${Y(y)}px)`;
    d.e.style.opacity = opacity;
    d.e.style.fill = fill;
  };

  // the overlays of the last three steps
  const ov = (html) => { const o = document.createElement("div"); o.className = "how-ov"; o.innerHTML = html; stage.appendChild(o); return o; };
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const pct = (v) => Math.round((v || 0) * 100).toLocaleString(C.rtl ? "ar-SY" : "en-GB") + (C.rtl ? "٪" : "%");
  const meter = (who, key) => `<div class="how-meter"><b>${esc(who)}</b><div class="trk"><span class="mk" data-v="${C.tone[key] ?? 0}"></span></div><span class="w">${esc(C.toneWords[key])}</span></div>`;
  const ovMood = ov(`<div class="card">${meter(C.people, "people")}${meter(C.outlets, "outlets")}<div class="how-ends"><span>${esc(C.ends[0])}</span><span>${esc(C.ends[1])}</span></div></div>`);
  const ovGap = ov(`<div class="card how-gap">${C.gap ? Object.entries(C.gap).map(([a, x]) => `<div class="a">${esc(C.areas[a])}</div>
      <div class="r"><span>${esc(C.people)}</span><span class="t"><span class="b p" data-w="${x.people}"></span></span><span class="v">${pct(x.people)}</span></div>
      <div class="r"><span>${esc(C.media)}</span><span class="t"><span class="b m" data-w="${x.media}"></span></span><span class="v">${pct(x.media)}</span></div>`).join("") : ""}</div>`);
  const ovOut = ov(`<div class="how-out">${C.outputs.map(([t, href], i) => href ? `<a href="${esc(href)}" style="transition-delay:${i * 0.08}s">${esc(t)}</a>` : `<span style="transition-delay:${i * 0.08}s">${esc(t)}</span>`).join("")}</div>`);
  const overlays = { 3: ovMood, 4: ovGap, 5: ovOut };

  const show = (el, on) => el.setAttribute("opacity", on ? 1 : 0);
  let current = -1;
  function go(step) {
    current = step;
    items.forEach((li, i) => li.classList.toggle("on", i === step));
    buttons.forEach((b, i) => (i === step ? b.setAttribute("aria-current", "step") : b.removeAttribute("aria-current")));
    srcLabels.forEach((t) => show(t, step <= 1));
    show(lPeople, step === 1); show(lOutlets, step === 1); show(lAside, step === 1);
    storyLabels.forEach((t) => show(t, step === 2));
    for (const [k, o] of Object.entries(overlays)) o.classList.toggle("on", Number(k) === step);
    if (step === 0) {
      // posts arrive from their sources: start at the source, then flow to the pile
      dots.forEach((d) => { d.e.style.transition = "none"; place(d, [140, srcY[d.src]], 1, NEUTRAL); });
      svg.getBoundingClientRect();
      dots.forEach((d) => { d.e.style.transition = ""; place(d, d.pile, 1, NEUTRAL, d.delay); });
    } else if (step === 1) {
      dots.forEach((d) => (d.drop ? place(d, d.out, 0, PALE, d.delay * 0.4) : place(d, d.lane, 1, d.people ? BRASS : GREY, d.delay * 0.4)));
    } else if (step === 2) {
      dots.forEach((d) => (d.drop ? place(d, d.out, 0, PALE) : place(d, d.cl, 1, d.people ? BRASS : GREY, d.delay * 0.3)));
    } else {
      dots.forEach((d) => (d.drop ? place(d, d.out, 0, PALE) : place(d, d.cl, 0.12, d.people ? BRASS : GREY)));
    }
    // the meters and bars move to today's values once their card is showing
    requestAnimationFrame(() => setTimeout(() => {
      ovMood.querySelectorAll(".mk").forEach((m) => (m.style.insetInlineStart = step === 3 ? `${((Number(m.dataset.v) + 1) / 2) * 100}%` : "50%"));
      ovGap.querySelectorAll(".b").forEach((b) => (b.style.width = step === 4 ? `${Math.max(1, Number(b.dataset.w) * 100)}%` : "0"));
    }, 60));
    restartBar();
  }

  // playing: one step every few seconds, round and round; a step chosen by hand pauses it
  let playing = !reduce, timer = null, started = false;
  function restartBar() {
    clearTimeout(timer);
    bar.style.transition = "none"; bar.style.width = "0";
    if (!playing) return;
    bar.getBoundingClientRect();
    bar.style.transition = `width ${STEP_MS}ms linear`; bar.style.width = "100%";
    timer = setTimeout(() => go((current + 1) % items.length), STEP_MS);
  }
  const setPlaying = (on) => { playing = on; pp.textContent = on ? C.pause : C.play; restartBar(); };
  pp.addEventListener("click", () => setPlaying(!playing));
  buttons.forEach((b, i) => b.addEventListener("click", () => { playing = false; pp.textContent = C.play; go(i); }));
  pp.textContent = playing ? C.pause : C.play;

  const start = () => { if (!started) { started = true; go(0); } };
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { start(); io.disconnect(); } }, { threshold: 0.3 });
    io.observe(stage);
  } else start();
  document.addEventListener("visibilitychange", () => { if (document.hidden) { clearTimeout(timer); } else if (started) restartBar(); });
})();
