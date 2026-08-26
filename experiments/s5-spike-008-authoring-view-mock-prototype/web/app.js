"use strict";

const fixtureUrl = "../fixtures/customer-complaint-quality-improvement.json";
let fixture;
let suggestionAccepted = false;

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[character]);

function showStep(number) {
  $$(".journey-panel").forEach((panel) => panel.classList.add("hidden"));
  $(`#step-${number}`).classList.remove("hidden");
  $$(".step").forEach((step) => step.classList.toggle("active", Number(step.dataset.step) === number));
}

function techRows(values) {
  return Object.entries(values).map(([key, value]) => {
    const display = Array.isArray(value) ? value.join(", ") : (typeof value === "object" ? JSON.stringify(value) : value);
    return `<div class="tech-row"><span>${escapeHtml(key.replaceAll("_", " "))}</span><code>${escapeHtml(display)}</code></div>`;
  }).join("");
}

function render() {
  $("#problem").value = fixture.scenario.business_prompt;
  $("#employee-cards").innerHTML = fixture.directory.map((employee) => `<article class="employee-card"><span class="chip">${escapeHtml(employee.status.replaceAll("_", " "))}</span><h3>${escapeHtml(employee.name)}</h3><strong>${escapeHtml(employee.role_title)}</strong><p>${escapeHtml(employee.role_description)}</p><small>Knowledge scope · ${escapeHtml(employee.knowledge_scope)}</small></article>`).join("");
  $("#plan").innerHTML = fixture.business_entry.work_plan.map((item) => `<li>${escapeHtml(item.label)}</li>`).join("");
  $("#outcome-summary").textContent = fixture.execution.outcome.summary;
  $("#recommendations").innerHTML = fixture.execution.outcome.recommendations.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  $("#progress-list").innerHTML = fixture.business_entry.work_plan.map((item) => `<div class="progress-item"><b>✓</b><span>${escapeHtml(item.label)}</span></div>`).join("");
  $("#citations").innerHTML = fixture.knowledge.assets.map((asset, index) => `<div class="citation"><b>${index + 1}</b><div><strong>${escapeHtml(asset.title)}</strong><br><small>${escapeHtml(asset.citation)}</small></div><span class="status success">Available</span></div>`).join("");
  const published = fixture.authoring.published;
  $("#published-card").textContent = `${published.name}\n${published.role_title}\n\n${published.role_description}\n\nStatus · ${published.status}\nVersion · ${published.version}`;
  $("#draft-role").value = published.role_description;
  const technical = fixture.views.technical;
  $("#technical-content").innerHTML = `<section class="tech-section"><h3>Identity chain</h3>${techRows({...technical, platform_execution_identity: fixture.execution.platform_execution_identity})}</section><section class="tech-section"><h3>Execution chain</h3>${techRows(fixture.execution)}</section><section class="tech-section"><h3>Knowledge evidence</h3>${techRows({collection_identity: fixture.knowledge.collection.id, authorization_decision: fixture.knowledge.authorization.decision, retrieved_evidence_ids: fixture.knowledge.assets.map((item) => item.evidence_id), fixture_version: fixture.knowledge.fixture_version, provider_native_correlation_id: fixture.knowledge.provider_correlation_id})}</section><section class="tech-section"><h3>Runtime support</h3>${fixture.runtime_support.map((item) => `<div class="support-card"><strong>${escapeHtml(item.runtime)} · ${escapeHtml(item.product_label)}</strong><small>${escapeHtml(item.technical_state)} · Support ${escapeHtml(item.support)}</small></div>`).join("")}</section><section class="tech-section"><h3>Error & limitation states</h3>${techRows({capability_denied:"DENY / zero Provider calls", ambiguous_effect:"UNKNOWN / no automatic retry", unsupported:"NOT_SUPPORTED", evidence_debt:"NOT_YET_PROVEN", exactly_once_claim:"NOT_MADE"})}</section>`;
}

function updateDiff() {
  const published = fixture.authoring.published;
  const roleChanged = $("#draft-role").value !== published.role_description;
  const rows = [];
  if (roleChanged) rows.push(["role description", published.role_description, $("#draft-role").value]);
  if (suggestionAccepted) rows.push(["responsibilities", published.business_responsibilities.join(" · "), fixture.authoring.ai_suggestion.candidate.join(" · ")]);
  $("#diff").innerHTML = `<h3>Field-level Diff</h3>${rows.length ? rows.map(([field, oldValue, newValue]) => `<div class="diff-row"><strong>${escapeHtml(field)}</strong><span class="old">${escapeHtml(oldValue)}</span><span class="new">${escapeHtml(newValue)}</span></div>`).join("") : "<p>No accepted changes yet.</p>"}`;
  $("#approve-draft").disabled = rows.length === 0;
}

function setTechnical(open) {
  $("#technical").classList.toggle("open", open);
  $("#technical").setAttribute("aria-hidden", String(!open));
  $("#scrim").classList.toggle("hidden", !open);
  $("#view-toggle").setAttribute("aria-pressed", String(open));
}

async function start() {
  const response = await fetch(fixtureUrl);
  if (!response.ok) throw new Error("Fixture unavailable");
  fixture = await response.json();
  render();
  $("#recommend").addEventListener("click", () => showStep(2));
  $("#confirm").addEventListener("click", () => { $("[data-execution-id]").textContent = fixture.execution.platform_execution_identity; showStep(3); });
  $$(".back").forEach((button) => button.addEventListener("click", () => showStep(button.closest("#step-3") ? 2 : 1)));
  $("#view-toggle").addEventListener("click", () => setTechnical(true));
  $("#close-technical").addEventListener("click", () => setTechnical(false));
  $("#scrim").addEventListener("click", () => setTechnical(false));
  $("#open-authoring").addEventListener("click", () => { $("#authoring").classList.remove("hidden"); $("#authoring").scrollIntoView({behavior:"smooth"}); });
  $("#draft-role").addEventListener("input", updateDiff);
  $("#accept-suggestion").addEventListener("click", () => { suggestionAccepted = true; $("#accept-suggestion").disabled = true; $("#accept-suggestion").textContent = "Accepted into Draft"; updateDiff(); });
  $("#reject-draft").addEventListener("click", () => { $("#draft-status").textContent = "Rejected · not published"; $("#draft-status").className = "status neutral"; });
  $("#approve-draft").addEventListener("click", () => { $("#draft-status").textContent = "Approved mock definition"; $("#draft-status").className = "status success"; $("#approve-draft").textContent = "Mock published in memory"; $("#approve-draft").disabled = true; });
}

start().catch((error) => { document.body.innerHTML = `<main><section class="panel"><h1>Prototype unavailable</h1><p>${escapeHtml(error.message)}. Serve the repository over HTTP so the deterministic fixture can load.</p></section></main>`; });
