"use strict";

const fixtureUrl = "../fixtures/customer-complaint-quality-improvement.json";
const defaultLocale = "en-US";
const supportedLocales = ["zh-CN", "en-US"];
let fixture;
let catalogs = {};
let currentLocale = "zh-CN";
let suggestionAccepted = false;

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[character]);
const t = (key, locale = currentLocale) => catalogs[locale]?.[key] || catalogs[defaultLocale]?.[key] || key;
const localized = () => fixture.localized_content[currentLocale] || fixture.localized_content[defaultLocale];

function showStep(number) {
  $$(".journey-panel").forEach((panel) => panel.classList.add("hidden"));
  $(`#step-${number}`).classList.remove("hidden");
  $$(".step").forEach((step) => step.classList.toggle("active", Number(step.dataset.step) === number));
}

function techRows(values, labels = {}) {
  return Object.entries(values).map(([key, value]) => {
    const display = Array.isArray(value) ? value.join(", ") : (typeof value === "object" ? JSON.stringify(value) : value);
    return `<div class="tech-row"><span>${escapeHtml(labels[key] || key.replaceAll("_", " "))}</span><code>${escapeHtml(display)}</code></div>`;
  }).join("");
}

function formatEvidence() {
  return {
    display_time: new Intl.DateTimeFormat(currentLocale, {dateStyle:"medium", timeStyle:"medium", timeZone:"UTC"}).format(new Date(fixture.execution.source_event_timestamp)),
    duration: new Intl.NumberFormat(currentLocale, {style:"unit", unit:"second", unitDisplay:"long"}).format(fixture.execution.duration_seconds),
    utilization: new Intl.NumberFormat(currentLocale, {style:"percent", maximumFractionDigits:0}).format(Number.parseFloat(fixture.execution.mock_utilization) / 100),
    provider_calls: new Intl.NumberFormat(currentLocale).format(fixture.execution.provider_call_count)
  };
}

function renderMessages() {
  document.documentElement.lang = currentLocale;
  $$('[data-i18n]').forEach((element) => { element.textContent = t(element.dataset.i18n); });
  $$('[data-i18n-aria]').forEach((element) => { element.setAttribute("aria-label", t(element.dataset.i18nAria)); });
  $$('[data-state-key]').forEach((element) => { element.textContent = t(element.dataset.stateKey); });
}

function render() {
  const content = localized();
  renderMessages();
  $("#employee-cards").innerHTML = fixture.directory.map((employee, index) => {
    const display = content.employees[index];
    return `<article class="employee-card"><span class="chip">${escapeHtml(employee.status)}</span><h3>${escapeHtml(employee.name)}</h3><strong>${escapeHtml(display.role_title)}</strong><p>${escapeHtml(display.role_description)}</p><p><b>${escapeHtml(t("knowledge.scope"))}</b> · ${escapeHtml(display.knowledge_scope)}</p><small>${display.can_do.map(escapeHtml).join(" · ")}<br>${display.cannot_do.map(escapeHtml).join(" · ")}</small></article>`;
  }).join("");
  $("#plan").innerHTML = content.work_plan.map((label) => `<li>${escapeHtml(label)}</li>`).join("");
  $("#outcome-summary").textContent = fixture.execution.outcome.summary;
  $("#recommendations").innerHTML = fixture.execution.outcome.recommendations.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  $("#progress-list").innerHTML = content.work_plan.map((label) => `<div class="progress-item"><b>✓</b><span>${escapeHtml(label)}</span></div>`).join("");
  $("#citations").innerHTML = fixture.knowledge.assets.map((asset, index) => `<div class="citation"><b>${new Intl.NumberFormat(currentLocale).format(index + 1)}</b><div><strong>${escapeHtml(content.knowledge_assets[index].title)}</strong><br><small>${escapeHtml(content.knowledge_assets[index].citation)}</small></div><span class="status success">${escapeHtml(t("citation.available"))}</span></div>`).join("");
  const published = fixture.authoring.published;
  $("#published-card").textContent = `${published.name}\n${content.employees[0].role_title}\n\n${content.employees[0].role_description}\n\nStatus · ${published.status}\nVersion · ${published.version}`;
  if (!$("#draft-role").dataset.edited) $("#draft-role").value = content.employees[0].role_description;
  const technical = fixture.views.technical;
  const formats = formatEvidence();
  const identityLabels = {digital_employee_definition:t("term.definition"), agent_definition_reference:t("term.definition"), instance_identity:t("term.instance"), task_identity:t("term.task"), workflow_reference:t("term.workflow"), runtime_provider_identity:t("term.provider"), provider_native_correlation_id:t("term.provider"), capability_request_identity:t("term.capability"), platform_execution_identity:t("term.executionIdentity")};
  const executionLabels = {platform_execution_identity:t("term.executionIdentity"), outcome:t("term.outcome"), requested_runtime:t("term.runtime"), effective_runtime:t("term.runtime"), runtime_target:t("term.runtime"), runtime_version:t("term.runtime"), runtime_binding:t("term.runtime"), capability_decision:t("term.capability"), provider_call_count:t("term.provider")};
  const knowledgeLabels = {collection_identity:t("term.enterpriseKnowledge"), authorization_decision:t("term.approval"), deny_decision:t("state.denied"), deny_provider_calls:t("term.provider"), retrieved_evidence_ids:t("term.evidence"), asset_revision_ids:t("term.enterpriseKnowledge"), fixture_version:t("term.evidence"), provider_native_correlation_id:t("term.provider")};
  const support = fixture.runtime_support.map((item) => `<div class="support-card"><strong>${escapeHtml(item.runtime)} · ${escapeHtml(t(`runtime.${item.runtime.toLowerCase()}.label`))}</strong><small>${escapeHtml(item.technical_state)} · Support ${escapeHtml(item.support)}</small>${item.runtime === "OpenClaw" ? `<small><code>LIVE_MANAGED_PROFILE_EVIDENCE_REQUIRED</code> · ${escapeHtml(t("reason.LIVE_MANAGED_PROFILE_EVIDENCE_REQUIRED"))}</small>` : ""}</div>`).join("");
  $("#technical-content").innerHTML = `<section class="tech-section"><h3>${escapeHtml(t("technical.identity"))}</h3>${techRows({...technical, platform_execution_identity:fixture.execution.platform_execution_identity}, identityLabels)}</section><section class="tech-section"><h3>${escapeHtml(t("technical.execution"))}</h3>${techRows(fixture.execution, executionLabels)}</section><section class="tech-section"><h3>${escapeHtml(t("technical.knowledge"))}</h3>${techRows({collection_identity:fixture.knowledge.collection.id, authorization_decision:fixture.knowledge.authorization.decision, deny_decision:fixture.knowledge.deny_evidence.decision, deny_provider_calls:fixture.knowledge.deny_evidence.provider_calls, retrieved_evidence_ids:fixture.knowledge.assets.map((item) => item.evidence_id), asset_revision_ids:fixture.knowledge.assets.map((item) => `${item.asset_id} / ${item.revision}`), fixture_version:fixture.knowledge.fixture_version, provider_native_correlation_id:fixture.knowledge.provider_correlation_id}, knowledgeLabels)}</section><section class="tech-section"><h3>${escapeHtml(t("technical.runtime"))}</h3>${support}</section><section class="tech-section"><h3>${escapeHtml(t("technical.errors"))}</h3>${techRows({capability_denied:"DENY / zero Provider calls", ambiguous_effect:"UNKNOWN / no automatic retry", unsupported:"NOT_SUPPORTED", evidence_debt:"NOT_YET_PROVEN", exactly_once_claim:"NOT_MADE"})}</section><section class="tech-section"><h3>${escapeHtml(t("term.evidence"))} · locale format</h3>${techRows({source_event_timestamp:fixture.execution.source_event_timestamp, display_time:formats.display_time, duration:formats.duration, utilization:formats.utilization, provider_calls:formats.provider_calls})}</section>`;
  updateDiff();
}

function updateDiff() {
  const publishedDescription = localized().employees[0].role_description;
  const roleChanged = $("#draft-role").value !== publishedDescription;
  const rows = [];
  if (roleChanged) rows.push([t("role.description"), publishedDescription, $("#draft-role").value]);
  if (suggestionAccepted) rows.push([t("outcome.recommendations"), localized().employees[0].business_responsibilities.join(" · "), t("suggestion.text")]);
  $("#diff").innerHTML = `<h3>${escapeHtml(t("diff.title"))}</h3>${rows.length ? rows.map(([field, oldValue, newValue]) => `<div class="diff-row"><strong>${escapeHtml(field)}</strong><span class="old">${escapeHtml(oldValue)}</span><span class="new">${escapeHtml(newValue)}</span></div>`).join("") : `<p>${escapeHtml(t("diff.empty"))}</p>`}`;
  $("#approve-draft").disabled = rows.length === 0 || $("#approve-draft").dataset.published === "true";
}

function setTechnical(open) {
  $("#technical").classList.toggle("open", open);
  $("#technical").setAttribute("aria-hidden", String(!open));
  $("#scrim").classList.toggle("hidden", !open);
  $("#view-toggle").setAttribute("aria-pressed", String(open));
}

async function start() {
  const [fixtureResponse, zhResponse, enResponse] = await Promise.all([fetch(fixtureUrl), fetch("../locales/zh-CN.json"), fetch("../locales/en-US.json")]);
  if (![fixtureResponse, zhResponse, enResponse].every((response) => response.ok)) throw new Error("Fixture or locale catalog unavailable");
  fixture = await fixtureResponse.json();
  catalogs = {"zh-CN":await zhResponse.json(), "en-US":await enResponse.json()};
  $("#problem").value = fixture.scenario.business_prompt;
  render();
  $("#locale").addEventListener("change", (event) => { currentLocale = supportedLocales.includes(event.target.value) ? event.target.value : defaultLocale; render(); });
  $("#recommend").addEventListener("click", () => showStep(2));
  $("#confirm").addEventListener("click", () => { $("[data-execution-id]").textContent = fixture.execution.platform_execution_identity; $("[data-execution-id]").removeAttribute("data-i18n"); showStep(3); });
  $$(".back").forEach((button) => button.addEventListener("click", () => showStep(button.closest("#step-3") ? 2 : 1)));
  $("#view-toggle").addEventListener("click", () => setTechnical(true));
  $("#close-technical").addEventListener("click", () => setTechnical(false));
  $("#scrim").addEventListener("click", () => setTechnical(false));
  $("#open-authoring").addEventListener("click", () => { $("#authoring").classList.remove("hidden"); $("#authoring").scrollIntoView({behavior:"smooth"}); });
  $("#draft-role").addEventListener("input", () => { $("#draft-role").dataset.edited = "true"; updateDiff(); });
  $("#accept-suggestion").addEventListener("click", () => { suggestionAccepted = true; $("#accept-suggestion").disabled = true; $("#accept-suggestion").dataset.stateKey = "suggestion.accepted"; render(); });
  $("#reject-draft").addEventListener("click", () => { $("#draft-status").dataset.stateKey = "status.rejected"; $("#draft-status").className = "status neutral"; renderMessages(); });
  $("#approve-draft").addEventListener("click", () => { $("#draft-status").dataset.stateKey = "status.approved"; $("#draft-status").className = "status success"; $("#approve-draft").dataset.stateKey = "status.published"; $("#approve-draft").dataset.published = "true"; render(); });
}

start().catch((error) => { document.body.innerHTML = `<main><section class="panel"><h1>Prototype unavailable</h1><p>${escapeHtml(error.message)}. Serve the repository over HTTP so the deterministic fixture can load.</p></section></main>`; });
