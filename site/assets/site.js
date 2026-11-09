// stellar-posture-watch interactive Web3 runtime
// Interactive workflow builder, issue simulator, and theme manager.

// Interactive Workflow Config Builder
(() => {
  const scheduleSelect = document.getElementById("builder-schedule");
  const gaugeRefInput = document.getElementById("builder-ref");
  const configInput = document.getElementById("builder-config");
  const breakBuildSelect = document.getElementById("builder-break");
  const outputCode = document.getElementById("workflow-output");

  if (!scheduleSelect || !outputCode) return;

  const updateWorkflow = () => {
    const schedule = scheduleSelect.value;
    const ref = gaugeRefInput?.value.trim() || "e6f47b2c019a3d4e5f6a7b8c9d0e1f2a3b4c5d6e";
    const config = configInput?.value.trim() || ".posture/gauge.toml";
    const breakBuild = breakBuildSelect?.value || "false";

    let cronStr = "0 6 * * 1"; // Monday 06:00 UTC
    let scheduleComment = "Every Monday at 06:00 UTC";
    if (schedule === "daily") {
      cronStr = "0 0 * * *";
      scheduleComment = "Every day at midnight UTC";
    } else if (schedule === "hourly") {
      cronStr = "0 * * * *";
      scheduleComment = "Every hour";
    }

    const yaml = `name: Stellar Posture Watch

on:
  schedule:
    # ${scheduleComment}
    - cron: "${cronStr}"
  workflow_dispatch:
    inputs:
      dry_run:
        description: "Dry run: test policy without modifying the tracking issue"
        required: false
        default: false
        type: boolean

permissions:
  contents: read
  issues: write

concurrency:
  group: posture-watch
  cancel-in-progress: false

jobs:
  watch:
    name: posture / watch
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository policy
        uses: actions/checkout@v4

      - name: Run Stellar Posture Watch
        uses: posture-sec/stellar-posture-watch@main
        with:
          gauge-ref: "${ref}"
          config: "${config}"
          break-build: "${breakBuild}"
          dry-run: \${{ inputs.dry_run || false }}
          github-token: \${{ secrets.GITHUB_TOKEN }}
`;
    outputCode.textContent = yaml;
  };

  [scheduleSelect, gaugeRefInput, configInput, breakBuildSelect].forEach((el) => {
    if (el) el.addEventListener("input", updateWorkflow);
  });

  updateWorkflow();
})();

// Sentinel Live Widget Simulator (Toggle Clean vs Drift state)
(() => {
  const tabs = document.querySelectorAll(".widget-tab");
  const issueContainer = document.getElementById("simulated-issue");
  if (!tabs.length || !issueContainer) return;

  const states = {
    clean: {
      badgeText: "0 Findings • Clean",
      badgeClass: "clean",
      bodyHtml: `
        <div class="issue-header">
          <div class="issue-title">
            <span>Account Posture Watch</span>
            <span class="issue-tag">account-posture</span>
          </div>
          <span class="issue-status-badge clean">● Clean Ledger</span>
        </div>
        <p style="margin:0 0 10px; color:#94a3b8; font-size:11.5px;">
          Audited against <b>horizon.stellar.org</b> at ledger <b>65,282,653</b> (2026-11-09 12:00 UTC).
        </p>
        <table class="issue-table">
          <thead>
            <tr>
              <th>Account</th>
              <th>Thresholds</th>
              <th>Signers</th>
              <th>Findings</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>GAAZI...5568</td>
              <td>2 / 2 / 2</td>
              <td>4 keys (weight 6)</td>
              <td style="color:#10b981;">0 findings</td>
            </tr>
          </tbody>
        </table>
        <div class="issue-footer">
          <span>State marker: <code><!-- posture-watch:v1:state --></code></span>
          <span>Next check: Monday 06:00 UTC</span>
        </div>
      `
    },
    drift: {
      badgeText: "2 Findings • Drift Detected",
      badgeClass: "drift",
      bodyHtml: `
        <div class="issue-header">
          <div class="issue-title">
            <span>Account Posture Watch</span>
            <span class="issue-tag">account-posture</span>
          </div>
          <span class="issue-status-badge drift">● Drift Alert</span>
        </div>
        <p style="margin:0 0 10px; color:#f43f5e; font-size:11.5px;">
          Audited against <b>horizon.stellar.org</b> at ledger <b>65,282,653</b> — 2 posture drifts detected!
        </p>
        <table class="issue-table">
          <thead>
            <tr>
              <th>Rule ID</th>
              <th>Severity</th>
              <th>Target</th>
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><code>sig-weight-drift</code></td>
              <td style="color:#f43f5e; font-weight:600;">HIGH</td>
              <td>GAAZI...5568</td>
              <td>Key GD3... signed weight reduced from 2 to 0</td>
            </tr>
            <tr>
              <td><code>id-unlisted-account</code></td>
              <td style="color:#f59e0b; font-weight:600;">WARN</td>
              <td>GAAZI...5568</td>
              <td>Account not listed in stellar.toml [ACCOUNTS]</td>
            </tr>
          </tbody>
        </table>
        <div class="issue-footer">
          <span>State marker: <code><!-- posture-watch:v1:state --></code></span>
          <span style="color:#f43f5e;">Action: Issue updated & notify team</span>
        </div>
      `
    }
  };

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("is-active"));
      tab.classList.add("is-active");
      const stateKey = tab.getAttribute("data-state") || "clean";
      const stateData = states[stateKey];
      if (stateData) {
        issueContainer.innerHTML = stateData.bodyHtml;
      }
    });
  });
})();

// Copy Button Logic with Toast
(() => {
  const copyButtons = document.querySelectorAll("[data-copy-target]");
  copyButtons.forEach((btn) => {
    btn.addEventListener("click", async () => {
      const targetId = btn.getAttribute("data-copy-target");
      const target = document.getElementById(targetId);
      if (!target) return;

      try {
        await navigator.clipboard.writeText(target.innerText);
        const originalText = btn.innerHTML;
        btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg> Copied!`;
        btn.classList.add("is-copied");
        setTimeout(() => {
          btn.innerHTML = originalText;
          btn.classList.remove("is-copied");
        }, 1800);
      } catch (err) {
        console.error("Failed to copy text:", err);
      }
    });
  });
})();

// Theme Toggle
(() => {
  const root = document.documentElement;
  const toggle = document.querySelector(".theme-toggle");
  if (!toggle) return;

  const currentTheme = localStorage.getItem("sentinel-theme") || "dark";
  root.dataset.theme = currentTheme;

  toggle.addEventListener("click", () => {
    const next = root.dataset.theme === "light" ? "dark" : "light";
    root.dataset.theme = next;
    localStorage.setItem("sentinel-theme", next);
  });
})();

// FAQ Accordion (Single-open mode)
(() => {
  const faqItems = document.querySelectorAll(".faq-item");
  faqItems.forEach((item) => {
    item.addEventListener("toggle", () => {
      if (item.open) {
        faqItems.forEach((other) => {
          if (other !== item && other.open) {
            other.removeAttribute("open");
          }
        });
      }
    });
  });
})();
