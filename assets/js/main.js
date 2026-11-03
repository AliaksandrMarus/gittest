// ===== БутузТранс =====

// ЗАМЕНИТЬ: e-mail, куда приходят заявки
const ORDER_EMAIL = "info@butuztrans.by";

// Километры на остановках маршрута — в том же порядке, что и .stop в разметке
const ROUTE_KM = [0, 720, 2500, 5150, 5820, 8600];

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const canAnimate = Boolean(window.gsap && window.ScrollTrigger) && !reducedMotion;

// ---------- Навигация ----------
const nav = document.getElementById("nav");
const burger = document.getElementById("burger");
const navLinks = document.getElementById("navLinks");

const updateNav = () => nav.classList.toggle("is-solid", window.scrollY > 40);
updateNav();
window.addEventListener("scroll", updateNav, { passive: true });

const setMenuOpen = (isOpen) => {
  navLinks.classList.toggle("is-open", isOpen);
  burger.setAttribute("aria-expanded", String(isOpen));
  burger.setAttribute("aria-label", isOpen ? "Закрыть меню" : "Открыть меню");
};
burger.addEventListener("click", () => setMenuOpen(!navLinks.classList.contains("is-open")));
navLinks.addEventListener("click", (event) => {
  if (event.target.tagName === "A") setMenuOpen(false);
});

// ---------- Hero: слово на всю ширину экрана ----------
const heroWord = document.getElementById("heroWord");
const zoomLetter = document.getElementById("zoomLetter");
const heroKnock = document.getElementById("heroKnock");

const fitHeroWord = () => {
  heroWord.style.fontSize = "100px";
  const byWidth = (100 * window.innerWidth * 0.94) / heroWord.scrollWidth;
  const byHeight = (100 * window.innerHeight * 0.5) / heroWord.scrollHeight;
  heroWord.style.fontSize = `${Math.min(byWidth, byHeight)}px`;
};

// Точка, в которую «влетаем»: ствол буквы Е, чтобы экран залило видео, а не фоном
const offsetWithin = (element, ancestor) => {
  let left = 0;
  let top = 0;
  for (let node = element; node && node !== ancestor; node = node.offsetParent) {
    left += node.offsetLeft;
    top += node.offsetTop;
  }
  return { left, top };
};

const setZoomOrigin = () => {
  const { left, top } = offsetWithin(zoomLetter, heroKnock);
  const x = left + zoomLetter.offsetWidth * 0.22;
  const y = top + zoomLetter.offsetHeight * 0.55;
  heroKnock.style.transformOrigin = `${x}px ${y}px`;
};

fitHeroWord();
setZoomOrigin();

// ---------- Анимации прокрутки ----------
if (canAnimate) {
  document.documentElement.classList.add("has-motion");
  gsap.registerPlugin(ScrollTrigger);

  ScrollTrigger.addEventListener("refreshInit", () => {
    fitHeroWord();
    setZoomOrigin();
  });

  // Hero: пролетаем сквозь букву, видео раскрывается на весь экран
  gsap.timeline({
    scrollTrigger: { trigger: ".hero", start: "top top", end: "+=160%", pin: true, scrub: 0.6, anticipatePin: 1 },
  })
    .to("#heroIntro", { autoAlpha: 0, y: 30, duration: 0.15, ease: "none" }, 0)
    .to(heroKnock, { scale: 40, duration: 1, ease: "power3.in" }, 0)
    .to(heroKnock, { autoAlpha: 0, duration: 0.2, ease: "none" }, 0.75)
    .to("#heroPaint", { opacity: 0.45, duration: 0.3, ease: "none" }, 0.7)
    .to("#heroShade", { opacity: 1, duration: 0.3, ease: "none" }, 0.8)
    .fromTo("#heroFinal", { autoAlpha: 0, y: 40 }, { autoAlpha: 1, y: 0, duration: 0.25, ease: "power2.out" }, 0.9);

  // Маршрут: лента едет влево, фура стоит, одометр крутит километры
  const track = document.getElementById("track");
  const odo = document.getElementById("odo");
  const dashes = document.getElementById("dashes");
  // у всех колёс общий символ, поэтому крутим один элемент
  const wheelSpin = document.querySelector("#wheel .tr-spin");
  const stopWidth = () => track.querySelector(".stop").offsetWidth;
  const trackDistance = () => track.scrollWidth - window.innerWidth;
  const formatKm = (km) => Math.round(km).toLocaleString("ru-RU");

  // Положение на маршруте: 2.5 — ровно посередине между 3-й и 4-й остановкой
  const stopPositionAt = (offset) => Math.min(offset / stopWidth(), ROUTE_KM.length - 1);

  const interpolate = (values, position) => {
    const index = Math.floor(position);
    const next = Math.min(index + 1, values.length - 1);
    return values[index] + (values[next] - values[index]) * (position - index);
  };

  // Мини-карта: длина линии до каждой остановки (Астана — промежуточная точка без остановки)
  const mapDone = document.getElementById("mapDone");
  const mapTruck = document.getElementById("mapTruck");
  const MAP_POINTS = [[78, 81], [145, 60], [329, 52], [415, 96], [487, 152], [545, 156], [775, 187]];
  const MAP_STOP_POINTS = [0, 1, 2, 4, 5, 6];
  const mapLengths = MAP_POINTS.reduce((lengths, point, i) => {
    if (i === 0) return [0];
    const [x0, y0] = MAP_POINTS[i - 1];
    return [...lengths, lengths[i - 1] + Math.hypot(point[0] - x0, point[1] - y0)];
  }, []);
  const mapStopLengths = MAP_STOP_POINTS.map((i) => mapLengths[i]);
  const mapTotal = mapDone.getTotalLength();
  mapDone.style.strokeDasharray = `${mapTotal}`;

  const updateMinimap = (position) => {
    const length = interpolate(mapStopLengths, position);
    const point = mapDone.getPointAtLength(length);
    mapDone.style.strokeDashoffset = `${mapTotal - length}`;
    mapTruck.setAttribute("cx", point.x);
    mapTruck.setAttribute("cy", point.y);
  };
  updateMinimap(0);

  // onUpdate у самой анимации, а не у ScrollTrigger: так одометр догоняет плавную прокрутку
  gsap.to(track, {
    x: () => -trackDistance(),
    ease: "none",
    onUpdate: () => {
      const offset = -gsap.getProperty(track, "x");
      const position = stopPositionAt(offset);
      odo.textContent = formatKm(interpolate(ROUTE_KM, position));
      updateMinimap(position);
      dashes.style.backgroundPositionX = `${-offset}px`;
      wheelSpin.setAttribute("transform", `rotate(${offset * 0.9})`);
    },
    scrollTrigger: {
      trigger: ".route",
      start: "top top",
      end: () => `+=${trackDistance()}`,
      pin: true,
      scrub: 0.5,
      invalidateOnRefresh: true,
    },
  });

  // Автопарк: надпись едет вслед за прокруткой, как борт проезжающей фуры
  gsap.fromTo("#fleetRun", { xPercent: 0 }, {
    xPercent: -30,
    ease: "none",
    scrollTrigger: { trigger: ".fleet", start: "top bottom", end: "bottom top", scrub: true },
  });

  document.fonts.ready.then(() => ScrollTrigger.refresh());
} else {
  document.fonts.ready.then(() => {
    fitHeroWord();
    setZoomOrigin();
  });
  window.addEventListener("resize", fitHeroWord);
}

// ---------- Видео ----------
const heroVideo = document.querySelector(".hero__video");
const servicesList = document.getElementById("services-list");
const canHover = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

// Остальные видео грузим и запускаем, только когда до них долистали
const lazyVideoObserver = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) entry.target.play().catch(() => {});
    else entry.target.pause();
  });
}, { rootMargin: "200px" });

// Направления: на компьютере ролик едет за курсором, на телефоне стоит в строке
const setupServicePreview = () => {
  const preview = document.createElement("figure");
  preview.className = "svc-preview";
  preview.setAttribute("aria-hidden", "true");
  const video = document.createElement("video");
  Object.assign(video, { muted: true, loop: true, playsInline: true });
  preview.append(video);
  document.body.append(preview);

  const placePreview = (() => {
    if (!window.gsap) return (x, y) => { preview.style.translate = `${x}px ${y}px`; };
    const moveX = gsap.quickTo(preview, "x", { duration: 0.45, ease: "power3" });
    const moveY = gsap.quickTo(preview, "y", { duration: 0.45, ease: "power3" });
    return (x, y) => { moveX(x); moveY(y); };
  })();

  servicesList.addEventListener("mousemove", (event) => {
    const fitsRight = event.clientX + 24 + preview.offsetWidth < window.innerWidth;
    const x = fitsRight ? event.clientX + 24 : event.clientX - 24 - preview.offsetWidth;
    placePreview(x, event.clientY - preview.offsetHeight / 2);
  });

  servicesList.querySelectorAll(".svc").forEach((row) => {
    row.addEventListener("mouseenter", () => {
      if (video.src !== row.dataset.video) video.src = row.dataset.video;
      video.play().catch(() => {});
      preview.classList.add("is-visible");
    });
  });
  servicesList.addEventListener("mouseleave", () => {
    preview.classList.remove("is-visible");
    video.pause();
  });
};

const setupServiceInlineVideos = () => {
  servicesList.querySelectorAll(".svc").forEach((row) => {
    const video = document.createElement("video");
    Object.assign(video, { muted: true, loop: true, playsInline: true, preload: "none", src: row.dataset.video });
    video.className = "svc__video";
    video.setAttribute("aria-hidden", "true");
    row.append(video);
    if (!reducedMotion) lazyVideoObserver.observe(video);
  });
};

if (canHover) setupServicePreview();
else setupServiceInlineVideos();

if (reducedMotion) {
  heroVideo.removeAttribute("autoplay");
  heroVideo.pause();
} else {
  document.querySelectorAll(".lazy-video").forEach((video) => lazyVideoObserver.observe(video));
}

// ---------- Заявка ----------
const form = document.getElementById("orderForm");
const formNote = document.getElementById("formNote");
const waybillNo = document.getElementById("waybillNo");

const makeWaybillNumber = () => {
  const now = new Date();
  const date = `${String(now.getFullYear()).slice(2)}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}`;
  return `BT-${date}-${Math.floor(100 + Math.random() * 900)}`;
};
waybillNo.textContent = `№ ${makeWaybillNumber()}`;

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const required = [...form.querySelectorAll("[required]")];
  const empty = required.filter((input) => !input.value.trim());
  required.forEach((input) => input.classList.toggle("is-invalid", !input.value.trim()));
  if (empty.length) {
    formNote.textContent = "Укажите, откуда и куда везти, и телефон для связи.";
    empty[0].focus();
    return;
  }

  const data = Object.fromEntries(new FormData(form));
  const number = waybillNo.textContent;
  const body = [
    `Заявка ${number}`,
    `Откуда: ${data.from}`,
    `Куда: ${data.to}`,
    `Груз: ${data.cargo || "не указан"}`,
    `Вес, т: ${data.weight || "не указан"}`,
    `Дата загрузки: ${data.date || "не указана"}`,
    `Имя: ${data.name || "не указано"}`,
    `Телефон: ${data.phone}`,
  ].join("\n");

  const subject = `Заявка на перевозку: ${data.from} — ${data.to}`;
  window.location.href = `mailto:${ORDER_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  formNote.textContent = `Заявка ${number} отправлена. Диспетчер перезвонит.`;
  form.reset();
  waybillNo.textContent = `№ ${makeWaybillNumber()}`;
});

document.getElementById("year").textContent = new Date().getFullYear();
