/* Demo application logic.
 *
 * DEFECTS (intentional, match the seeded demo defects):
 *   - Temperatures are displayed in Fahrenheit instead of Celsius.
 *   - A failed search does NOT clear previously displayed weather.
 * Both are exercised by the Playwright suite and surface as UAT failures.
 */
'use strict';

const form = document.getElementById('search-form');
const cityInput = document.getElementById('city');
const errorEl = document.getElementById('error');
const currentEl = document.getElementById('current');
const forecastEl = document.getElementById('forecast');

function cToF(celsius) {
  return (celsius * 9) / 5 + 32; // DEFECT: UI displays °F although it claims °C
}

function fmt(value, unit) {
  return `${Math.round(value)}${unit}`;
}

function showError(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
  // DEFECT: does not clear the existing weather content.
}

async function search(city) {
  errorEl.hidden = true;
  const encoded = encodeURIComponent(city.trim());
  const [currentResp, forecastResp] = await Promise.all([
    fetch(`/api/weather/current/${encoded}`),
    fetch(`/api/weather/forecast/${encoded}?days=5`),
  ]);

  if (!currentResp.ok) {
    const body = await currentResp.json().catch(() => ({}));
    showError(body.error || `City "${city}" was not found.`);
    return;
  }

  const current = await currentResp.json();
  const forecast = await forecastResp.json();

  document.getElementById('city-name').textContent = `${current.city} · ${current.country}`;
  document.getElementById('condition').textContent = current.condition;
  document.getElementById('temperature').textContent =
    fmt(cToF(current.temperature_c), '°F'); // DEFECT: should be °C
  document.getElementById('feels-like').textContent =
    fmt(cToF(current.feels_like_c), '°F'); // DEFECT: should be °C
  document.getElementById('humidity').textContent = `${current.humidity}%`;
  document.getElementById('wind').textContent = `${current.wind_kph} km/h`;
  document.getElementById('pressure').textContent = `${current.pressure_hpa} hPa`;
  currentEl.hidden = false;

  const list = document.getElementById('forecast-list');
  list.replaceChildren();
  for (const day of forecast.days) {
    const div = document.createElement('div');
    div.className = 'forecast-day';
    div.innerHTML = `
      <div class="day">${day.date}</div>
      <div>${day.condition}</div>
      <div class="range">${fmt(cToF(day.temp_min_c), '°')} / ${fmt(cToF(day.temp_max_c), '°')}</div>
    `;
    list.appendChild(div);
  }
  forecastEl.hidden = false;
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  search(cityInput.value);
});
