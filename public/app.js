const form = document.querySelector("#booking-form");
const eventDateInput = document.querySelector("#event-date");
const slotPicker = document.querySelector("#slot-picker");
const slotList = document.querySelector("#slot-list");
const timeSlotInput = document.querySelector("#time-slot");
const slotHint = document.querySelector("#slot-hint");
const formStatus = document.querySelector("#form-status");
const visualSlides = Array.from(document.querySelectorAll("[data-visual-slide]"));
const visualDots = Array.from(document.querySelectorAll("[data-visual-dot]"));
const visualImages = Array.from(document.querySelectorAll("[data-visual-image]"));
const bioTrigger = document.querySelector("#bio-trigger");
const bioModal = document.querySelector("#bio-modal");
const bioCloseButtons = Array.from(document.querySelectorAll("[data-bio-close]"));
const bioClosePrimary = document.querySelector(".bio-close");

let availabilityState = {
  timeSlots: [],
  bookedSlots: {},
  dateRange: null,
};

const DATE_FORMATTER = new Intl.DateTimeFormat("et-EE", {
  day: "numeric",
  month: "long",
});

function formatHumanDate(dateString) {
  const parsed = new Date(`${dateString}T12:00:00`);
  return DATE_FORMATTER.format(parsed);
}

function showStatus(message, type = "") {
  formStatus.textContent = message;
  formStatus.className = `form-status ${type}`.trim();
}

function ensureVisualImageLoaded(index) {
  const image = visualImages[index];
  if (!image || image.dataset.loaded === "true") return;

  const nextSrc = image.dataset.src;
  if (!nextSrc) return;

  image.src = nextSrc;
  image.dataset.loaded = "true";
}

function setupVisualRotation() {
  if (visualSlides.length < 2) return;

  let activeIndex = 0;

  const renderVisualState = (nextIndex) => {
    ensureVisualImageLoaded(nextIndex);
    ensureVisualImageLoaded((nextIndex + 1) % visualSlides.length);

    visualSlides.forEach((slide, index) => {
      slide.classList.toggle("is-active", index === nextIndex);
    });

    visualDots.forEach((dot, index) => {
      dot.classList.toggle("is-active", index === nextIndex);
    });

    activeIndex = nextIndex;
  };

  ensureVisualImageLoaded(0);
  ensureVisualImageLoaded(1);

  window.setTimeout(() => {
    let preloadIndex = 2;

    const preloadRemaining = () => {
      if (preloadIndex >= visualSlides.length) return;
      ensureVisualImageLoaded(preloadIndex);
      preloadIndex += 1;
      window.setTimeout(preloadRemaining, 700);
    };

    preloadRemaining();
  }, 1200);

  window.setInterval(() => {
    const nextIndex = (activeIndex + 1) % visualSlides.length;
    renderVisualState(nextIndex);
  }, 4200);
}

function setupBioModal() {
  if (!bioTrigger || !bioModal) return;

  let closeTimer = null;

  const openBioModal = () => {
    if (closeTimer) {
      window.clearTimeout(closeTimer);
      closeTimer = null;
    }

    bioModal.hidden = false;
    document.body.classList.add("modal-open");
    bioTrigger.setAttribute("aria-expanded", "true");

    window.requestAnimationFrame(() => {
      bioModal.classList.add("is-open");
      bioClosePrimary?.focus();
    });
  };

  const closeBioModal = () => {
    bioModal.classList.remove("is-open");
    document.body.classList.remove("modal-open");
    bioTrigger.setAttribute("aria-expanded", "false");

    closeTimer = window.setTimeout(() => {
      bioModal.hidden = true;
      bioTrigger.focus();
    }, 240);
  };

  bioTrigger.addEventListener("click", openBioModal);
  bioCloseButtons.forEach((button) => button.addEventListener("click", closeBioModal));

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !bioModal.hidden) {
      closeBioModal();
    }
  });
}

function renderSlots() {
  const selectedDate = eventDateInput.value;
  timeSlotInput.value = "";

  if (!selectedDate) {
    slotPicker.hidden = true;
    slotHint.textContent = "Vali sobiv aeg";
    slotList.innerHTML = "";
    return;
  }

  slotPicker.hidden = false;
  const bookedSlotsForDate = availabilityState.bookedSlots[selectedDate] || [];
  const availableCount = availabilityState.timeSlots.filter((slot) => !bookedSlotsForDate.includes(slot)).length;

  slotHint.textContent =
    availableCount > 0
      ? `${availableCount} algusaega saadaval ${formatHumanDate(selectedDate)}`
      : "Sellel kuupäeval on kõik ajad täitunud";

  slotList.innerHTML = availabilityState.timeSlots
    .map((slot) => {
      const isBooked = bookedSlotsForDate.includes(slot);
      return `
        <button
          type="button"
          class="slot-button ${isBooked ? "disabled" : ""}"
          data-slot="${slot}"
          ${isBooked ? "disabled" : ""}
        >
          ${slot}
        </button>
      `;
    })
    .join("");

  slotList.querySelectorAll("[data-slot]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.disabled) return;
      slotList.querySelectorAll(".slot-button").forEach((item) => item.classList.remove("selected"));
      button.classList.add("selected");
      timeSlotInput.value = button.dataset.slot || "";
      slotHint.textContent = `Valitud aeg: ${formatHumanDate(selectedDate)} kell ${timeSlotInput.value}`;
    });
  });
}

async function fetchAvailability() {
  const response = await fetch("/api/availability");
  if (!response.ok) {
    throw new Error("Saadavuse laadimine ebaõnnestus.");
  }

  availabilityState = await response.json();
  if (availabilityState.dateRange) {
    eventDateInput.min = availabilityState.dateRange.min;
    eventDateInput.max = availabilityState.dateRange.max;
  }

  renderSlots();
}

async function handleSubmit(event) {
  event.preventDefault();

  showStatus("Päringut saadetakse...");
  const submitButton = form.querySelector('button[type="submit"]');
  submitButton.disabled = true;

  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());

  try {
    const response = await fetch("/api/bookings", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const result = await response.json();

    if (!response.ok) {
      const message = result.errors?.join(" ") || result.error || "Päringu saatmine ebaõnnestus.";
      throw new Error(message);
    }

    showStatus(result.message || "Päring saadetud.", "success");
    form.reset();
    timeSlotInput.value = "";
    await fetchAvailability();
  } catch (error) {
    showStatus(error.message || "Päringu saatmine ebaõnnestus.", "error");
  } finally {
    submitButton.disabled = false;
  }
}

function setupReveal() {
  const elements = document.querySelectorAll(".reveal");
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.18 }
  );

  elements.forEach((element) => observer.observe(element));
}

eventDateInput.addEventListener("change", renderSlots);
form.addEventListener("submit", handleSubmit);

setupReveal();
setupVisualRotation();
setupBioModal();
fetchAvailability().catch((error) => {
  showStatus(error.message || "Saadavuse laadimine ebaõnnestus.", "error");
});
