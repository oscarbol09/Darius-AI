/* ==============================================================================
   DARIUS AI — DOCUMENTATION PORTAL JAVASCRIPT
   Fast Client-Side Interactivity, Search, Tabs & ScrollSpy
   ============================================================================== */

document.addEventListener("DOMContentLoaded", () => {
  initMobileNav();
  initCodeCopy();
  initTabs();
  initScrollSpy();
  initSearch();
});

/* ── Mobile Sidebar Drawer ───────────────────────────────────────────────── */
function initMobileNav() {
  const toggleBtn = document.getElementById("menuToggle");
  const sidebar = document.getElementById("sidebar");
  if (!toggleBtn || !sidebar) return;

  toggleBtn.addEventListener("click", () => {
    sidebar.classList.toggle("open");
  });

  // Close sidebar on link click (mobile)
  document.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", () => {
      if (window.innerWidth <= 1024) {
        sidebar.classList.remove("open");
      }
    });
  });

  // Close if clicked outside
  document.addEventListener("click", (e) => {
    if (window.innerWidth <= 1024 && sidebar.classList.contains("open")) {
      if (!sidebar.contains(e.target) && !toggleBtn.contains(e.target)) {
        sidebar.classList.remove("open");
      }
    }
  });
}

/* ── Copy Code Snippets ─────────────────────────────────────────────────── */
function initCodeCopy() {
  document.querySelectorAll(".btn-copy").forEach((button) => {
    button.addEventListener("click", async () => {
      const codeBox = button.closest(".code-box");
      const codeEl = codeBox ? codeBox.querySelector("pre code") : null;
      if (!codeEl) return;

      const codeText = codeEl.innerText;
      try {
        await navigator.clipboard.writeText(codeText);
        const originalText = button.innerHTML;
        button.innerHTML = "✓ Copiado";
        button.style.color = "#34D399";

        setTimeout(() => {
          button.innerHTML = originalText;
          button.style.color = "";
        }, 2000);
      } catch (err) {
        console.error("No se pudo copiar el texto:", err);
      }
    });
  });
}

/* ── Interactive Tabs ────────────────────────────────────────────────────── */
function initTabs() {
  document.querySelectorAll(".tabs-container").forEach((container) => {
    const buttons = container.querySelectorAll(".tab-btn");
    const contents = container.querySelectorAll(".tab-content");

    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetTab = btn.getAttribute("data-tab");

        buttons.forEach((b) => b.classList.remove("active"));
        contents.forEach((c) => c.classList.remove("active"));

        btn.classList.add("active");
        const activeContent = container.querySelector(`#tab-${targetTab}`);
        if (activeContent) {
          activeContent.classList.add("active");
        }
      });
    });
  });
}

/* ── ScrollSpy (Active Section Highlighting) ─────────────────────────────── */
function initScrollSpy() {
  const sections = document.querySelectorAll("section[id]");
  const navLinks = document.querySelectorAll(".nav-link[href^='#']");

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const id = entry.target.getAttribute("id");
          navLinks.forEach((link) => {
            const href = link.getAttribute("href");
            if (href === `#${id}`) {
              link.classList.add("active");
            } else {
              link.classList.remove("active");
            }
          });
        }
      });
    },
    { rootMargin: "-80px 0px -70% 0px" }
  );

  sections.forEach((sec) => observer.observe(sec));
}

/* ── Instant Search Filter ───────────────────────────────────────────────── */
function initSearch() {
  const searchInput = document.getElementById("searchInput");
  if (!searchInput) return;

  const searchableElements = document.querySelectorAll(
    "section[id], .card, tr, .code-box"
  );

  searchInput.addEventListener("input", (e) => {
    const query = e.target.value.toLowerCase().trim();
    if (!query) {
      searchableElements.forEach((el) => {
        if (el.tagName === "TR") el.style.display = "";
        else if (el.classList.contains("card")) el.style.display = "";
      });
      return;
    }

    // Filter table rows
    document.querySelectorAll("tbody tr").forEach((row) => {
      const text = row.innerText.toLowerCase();
      row.style.display = text.includes(query) ? "" : "none";
    });

    // Filter cards
    document.querySelectorAll(".card").forEach((card) => {
      const text = card.innerText.toLowerCase();
      card.style.display = text.includes(query) ? "" : "none";
    });
  });
}
