(function () {
  "use strict";

  /* ---------- Mobile nav toggle ---------- */
  var navToggle = document.getElementById("navToggle");
  var primaryNav = document.getElementById("primaryNav");

  function closeNav() {
    if (!primaryNav || !navToggle) return;
    primaryNav.classList.remove("is-open");
    navToggle.setAttribute("aria-expanded", "false");
  }

  function toggleNav() {
    if (!primaryNav || !navToggle) return;
    var isOpen = primaryNav.classList.toggle("is-open");
    navToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
  }

  if (navToggle && primaryNav) {
    navToggle.addEventListener("click", toggleNav);

    primaryNav.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", closeNav);
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeNav();
    });
  }

  /* ---------- Hero video: graceful fallback to poster ---------- */
  var heroVideos = document.querySelectorAll(".hero-video");
  var prefersReducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  heroVideos.forEach(function (video) {
    function fallbackToPoster() {
      video.style.display = "none";
    }

    if (prefersReducedMotion) {
      fallbackToPoster();
      return;
    }

    video.addEventListener("error", fallbackToPoster, true);

    var playPromise = video.play();
    if (playPromise && typeof playPromise.catch === "function") {
      playPromise.catch(function () {
        /* Autoplay blocked or source missing/placeholder — poster stays visible. */
        fallbackToPoster();
      });
    }

    // Placeholder source files ship as empty/near-empty stand-ins until the
    // real generated clips are dropped in (see ASSETS.md) — treat "no data
    // after a beat" the same as an error so we don't show a black frame.
    setTimeout(function () {
      if (video.readyState === 0) fallbackToPoster();
    }, 2500);
  });

  /* ---------- Reveal-on-scroll ---------- */
  var revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && revealEls.length) {
    var revealObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            revealObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );
    revealEls.forEach(function (el) {
      revealObserver.observe(el);
    });
  } else {
    revealEls.forEach(function (el) {
      el.classList.add("is-visible");
    });
  }

  /* ---------- FAQ accordion (single-open) ---------- */
  var faqItems = document.querySelectorAll(".faq-item");
  faqItems.forEach(function (item) {
    item.addEventListener("toggle", function () {
      if (!item.open) return;
      faqItems.forEach(function (other) {
        if (other !== item) other.removeAttribute("open");
      });
    });
  });

  /* ---------- Lightweight analytics hooks (no-op until a counter is wired) ---------- */
  function trackEvent(name, params) {
    try {
      if (typeof window.gtag === "function") {
        window.gtag("event", name, params || {});
      }
      if (typeof window.ym === "function" && window.YM_COUNTER_ID) {
        window.ym(window.YM_COUNTER_ID, "reachGoal", name);
      }
    } catch (err) {
      /* Analytics must never break the page. */
    }
  }

  document.querySelectorAll('a[href^="tel:"]').forEach(function (link) {
    link.addEventListener("click", function () {
      trackEvent("phone_click");
    });
  });

  document
    .querySelectorAll('a[href*="wa.me"], a[href*="t.me"], a[href*="viber://"]')
    .forEach(function (link) {
      link.addEventListener("click", function () {
        trackEvent("messenger_click");
      });
    });

  /* ---------- Contact form ---------- */
  var forms = document.querySelectorAll(".contact-form");
  forms.forEach(function (form) {
    var status = form.querySelector(".form-status");
    var submitBtn = form.querySelector('button[type="submit"]');

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!status) return;

      var action = form.getAttribute("action") || "";
      if (!action || action.indexOf("REPLACE_WITH_FORM_ID") !== -1) {
        showStatus(
          "Форма ещё не подключена. Пожалуйста, позвоните нам напрямую — номер указан выше.",
          "error"
        );
        return;
      }

      if (submitBtn) submitBtn.disabled = true;
      showStatus("Отправляем заявку…", "pending");

      fetch(action, {
        method: "POST",
        headers: { Accept: "application/json" },
        body: new FormData(form),
      })
        .then(function (response) {
          if (response.ok) {
            form.reset();
            showStatus(
              "Спасибо! Заявка отправлена, мы перезвоним в ближайшее время.",
              "success"
            );
            trackEvent("lead_sent");
          } else {
            showStatus(
              "Не получилось отправить форму. Позвоните нам — так будет быстрее.",
              "error"
            );
          }
        })
        .catch(function () {
          showStatus(
            "Нет связи с сервером формы. Позвоните нам — так будет быстрее.",
            "error"
          );
        })
        .finally(function () {
          if (submitBtn) submitBtn.disabled = false;
        });
    });

    function showStatus(text, kind) {
      if (!status) return;
      status.textContent = text;
      status.classList.remove("is-success", "is-error");
      status.classList.add(
        "is-visible",
        kind === "success" ? "is-success" : kind === "error" ? "is-error" : ""
      );
    }
  });
})();
