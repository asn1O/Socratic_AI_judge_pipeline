/**
 * Socratic AI Annotation Studio - Frontend Controller
 */

// Application State
const state = {
  currentSample: 'random_sample',
  currentId: null,
  currentIndex: 1,
  totalCount: 0,
  prevId: null,
  nextId: null,
  conversations: [], // list of { id, is_graded }
  scores: {
    socratic_guidance: null,
    scaffolding: null,
    state_adaptation: null,
    diagnosis: null,
    student_agency: null,
    progression: null,
    coherence: null,
    correctness: null,
    overall_score_out_of_5: null,
    overall_score_out_of_10: null,
  },
  fontSize: 14,
  rubricData: null,
};

// DOM Elements
const elements = {
  sampleTabs: document.getElementById('sample-tabs'),
  convSelect: document.getElementById('conv-select'),
  convQuickJump: document.getElementById('conv-quick-jump'),
  btnPrev: document.getElementById('btn-prev'),
  btnNext: document.getElementById('btn-next'),
  btnNextUngraded: document.getElementById('btn-next-ungraded'),
  progressCount: document.getElementById('progress-count'),
  progressPct: document.getElementById('progress-pct'),
  progressFill: document.getElementById('progress-fill'),
  metaAnnId: document.getElementById('meta-ann-id'),
  metaDomain: document.getElementById('meta-domain'),
  metaTopic: document.getElementById('meta-topic'),
  metaStatus: document.getElementById('meta-status'),
  metaProblem: document.getElementById('meta-problem'),
  specialInfoBox: document.getElementById('special-info-box'),
  metaConfigGrid: document.getElementById('meta-config-grid'),
  dialogueContainer: document.getElementById('dialogue-container'),
  judgeRefDrawer: document.getElementById('judge-ref-drawer'),
  judgeRefContent: document.getElementById('judge-ref-content'),
  gradingBadge: document.getElementById('grading-badge'),
  gradingTargetSheet: document.getElementById('grading-target-sheet'),
  scoreOutOf5: document.getElementById('score-out-of-5'),
  scoreOutOf10: document.getElementById('score-out-of-10'),
  syncScoresCheckbox: document.getElementById('sync-scores-checkbox'),
  btnSaveNext: document.getElementById('btn-save-next'),
  btnSaveOnly: document.getElementById('btn-save-only'),
  btnResetForm: document.getElementById('btn-reset-form'),
  btnRubricModal: document.getElementById('btn-rubric-modal'),
  btnCloseRubric: document.getElementById('btn-close-rubric'),
  rubricModal: document.getElementById('rubric-modal'),
  rubricModalContent: document.getElementById('rubric-modal-content'),
  btnThemeToggle: document.getElementById('btn-theme-toggle'),
  btnZoomIn: document.getElementById('btn-zoom-in'),
  btnZoomOut: document.getElementById('btn-zoom-out'),
  toastBanner: document.getElementById('toast-banner'),
  btnToggleAllGuides: document.getElementById('btn-toggle-all-guides'),
  rubricCheatBody: document.getElementById('rubric-cheat-body'),
  metaSourcePath: document.getElementById('meta-source-path'),
  metaSourceIndex: document.getElementById('meta-source-index'),
  btnCopyPath: document.getElementById('btn-copy-path'),
};

// Initialization
document.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  setupEventListeners();
  await initRubricData();
  await loadSamples();
});

// Theme Management
function initTheme() {
  const savedTheme = localStorage.getItem('socratic_theme') || 'theme-light';
  document.body.className = savedTheme;
  updateThemeIcon(savedTheme);
}

function toggleTheme() {
  const current = document.body.className.includes('theme-dark') ? 'theme-dark' : 'theme-light';
  const newTheme = current === 'theme-dark' ? 'theme-light' : 'theme-dark';
  document.body.className = newTheme;
  localStorage.setItem('socratic_theme', newTheme);
  updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
  elements.btnThemeToggle.textContent = theme === 'theme-dark' ? '☀️' : '🌙';
}

// Event Listeners
function setupEventListeners() {
  elements.btnThemeToggle.addEventListener('click', toggleTheme);

  // Zoom controls
  elements.btnZoomIn.addEventListener('click', () => {
    if (state.fontSize < 20) {
      state.fontSize += 1;
      applyFontSize();
    }
  });

  elements.btnZoomOut.addEventListener('click', () => {
    if (state.fontSize > 12) {
      state.fontSize -= 1;
      applyFontSize();
    }
  });

  // Navigation controls
  elements.convSelect.addEventListener('change', (e) => {
    const selectedId = e.target.value;
    if (selectedId) loadConversation(selectedId);
  });

  elements.convQuickJump.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      handleQuickJump();
    }
  });

  elements.btnPrev.addEventListener('click', () => {
    if (state.prevId) loadConversation(state.prevId);
  });

  elements.btnNext.addEventListener('click', () => {
    if (state.nextId) loadConversation(state.nextId);
  });

  elements.btnNextUngraded.addEventListener('click', jumpToNextUngraded);

  // Score Pills Interaction & Live Hint
  document.querySelectorAll('.score-pills').forEach((group) => {
    const field = group.dataset.field;
    group.querySelectorAll('.pill').forEach((pill) => {
      pill.addEventListener('click', () => {
        const val = parseInt(pill.dataset.val, 10);
        if (state.scores[field] === val) {
          state.scores[field] = null;
          pill.classList.remove('selected');
        } else {
          state.scores[field] = val;
          group.querySelectorAll('.pill').forEach((p) => p.classList.remove('selected'));
          pill.classList.add('selected');
        }
        updateMetricHint(field);
      });

      pill.addEventListener('mouseenter', () => {
        const val = parseInt(pill.dataset.val, 10);
        updateMetricHint(field, val);
      });

      pill.addEventListener('mouseleave', () => {
        updateMetricHint(field);
      });
    });
  });

  // Boolean Pills Interaction & Live Hint
  document.querySelectorAll('.bool-pills').forEach((group) => {
    const field = group.dataset.field;
    group.querySelectorAll('.pill-bool').forEach((pill) => {
      pill.addEventListener('click', () => {
        const val = pill.dataset.val === 'true';
        if (state.scores[field] === val) {
          state.scores[field] = null;
          pill.classList.remove('selected');
        } else {
          state.scores[field] = val;
          group.querySelectorAll('.pill-bool').forEach((p) => p.classList.remove('selected'));
          pill.classList.add('selected');
        }
        updateMetricHint(field);
      });

      pill.addEventListener('mouseenter', () => {
        const val = pill.dataset.val === 'true' ? 'TRUE' : 'FALSE';
        updateMetricHint(field, val);
      });

      pill.addEventListener('mouseleave', () => {
        updateMetricHint(field);
      });
    });
  });

  // Individual Metric Guide toggle buttons
  document.querySelectorAll('.btn-metric-guide').forEach((btn) => {
    btn.addEventListener('click', () => {
      const metric = btn.dataset.metric;
      const box = document.getElementById(`guide-${metric}`);
      if (box) {
        const isVisible = box.style.display !== 'none';
        box.style.display = isVisible ? 'none' : 'flex';
        btn.classList.toggle('active', !isVisible);
      }
    });
  });

  // Toggle all guides button
  let allGuidesExpanded = false;
  if (elements.btnToggleAllGuides) {
    elements.btnToggleAllGuides.addEventListener('click', () => {
      allGuidesExpanded = !allGuidesExpanded;
      document.querySelectorAll('.metric-guide-box').forEach((box) => {
        box.style.display = allGuidesExpanded ? 'flex' : 'none';
      });
      document.querySelectorAll('.btn-metric-guide').forEach((btn) => {
        btn.classList.toggle('active', allGuidesExpanded);
      });
      elements.btnToggleAllGuides.textContent = allGuidesExpanded
        ? '📕 Hide All Criteria'
        : '📖 Show All Criteria';
    });
  }

  // Score Inputs & Sync
  elements.scoreOutOf5.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value);
    state.scores.overall_score_out_of_5 = isNaN(val) ? null : val;
    if (elements.syncScoresCheckbox.checked && !isNaN(val)) {
      const tenVal = Math.min(10, Math.round(val * 2 * 10) / 10);
      elements.scoreOutOf10.value = tenVal;
      state.scores.overall_score_out_of_10 = tenVal;
    }
  });

  elements.scoreOutOf10.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value);
    state.scores.overall_score_out_of_10 = isNaN(val) ? null : val;
  });

  // Action Buttons
  elements.btnSaveNext.addEventListener('click', () => saveScores(true));
  elements.btnSaveOnly.addEventListener('click', () => saveScores(false));
  elements.btnResetForm.addEventListener('click', () => resetScoresForm(true));

  // Copy Relative Path Button
  if (elements.btnCopyPath) {
    elements.btnCopyPath.addEventListener('click', () => {
      const pathText = elements.metaSourcePath ? elements.metaSourcePath.textContent.trim() : '';
      if (pathText && pathText !== '-') {
        navigator.clipboard.writeText(pathText).then(() => {
          showToast('✓ Relative path copied to clipboard!', 'success');
        }).catch(() => {
          showToast(`Relative path: ${pathText}`, 'info');
        });
      }
    });
  }

  // Rubric Modal
  elements.btnRubricModal.addEventListener('click', openRubricModal);
  elements.btnCloseRubric.addEventListener('click', closeRubricModal);
  elements.rubricModal.addEventListener('click', (e) => {
    if (e.target === elements.rubricModal) closeRubricModal();
  });

  // Global Keyboard Shortcuts
  window.addEventListener('keydown', (e) => {
    // Save & Next: Alt + Enter or Ctrl + S
    if ((e.altKey && e.key === 'Enter') || (e.ctrlKey && e.key.toLowerCase() === 's')) {
      e.preventDefault();
      saveScores(true);
      return;
    }
    // Alt + Left: Prev
    if (e.altKey && e.key === 'ArrowLeft') {
      e.preventDefault();
      if (state.prevId) loadConversation(state.prevId);
      return;
    }
    // Alt + Right: Next
    if (e.altKey && e.key === 'ArrowRight') {
      e.preventDefault();
      if (state.nextId) loadConversation(state.nextId);
      return;
    }
  });
}

function applyFontSize() {
  document.querySelectorAll('.turn-content, .problem-text').forEach((el) => {
    el.style.fontSize = `${state.fontSize}px`;
  });
}

// Load Samples and render tabs
async function loadSamples() {
  try {
    const res = await fetch('/api/samples');
    const data = await res.json();
    if (!data.samples) return;

    elements.sampleTabs.innerHTML = '';
    data.samples.forEach((sample, idx) => {
      const btn = document.createElement('button');
      btn.className = `tab-btn ${sample.key === state.currentSample ? 'active' : ''}`;
      btn.dataset.sample = sample.key;
      btn.innerHTML = `${sample.display_name} <span style="opacity: 0.8; font-size: 11px;">(${sample.graded}/${sample.total})</span>`;
      btn.addEventListener('click', () => switchSample(sample.key));
      elements.sampleTabs.appendChild(btn);
    });

    await loadConversationList(state.currentSample);
  } catch (err) {
    showToast(`Failed to load samples: ${err.message}`, 'error');
  }
}

// Switch Active Sample
async function switchSample(sampleKey) {
  if (state.currentSample === sampleKey) return;
  state.currentSample = sampleKey;

  // Update tabs active class
  document.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.sample === sampleKey);
  });

  await loadConversationList(sampleKey);
}

// Load conversation IDs for current sample
async function loadConversationList(sampleKey, selectId = null) {
  try {
    const res = await fetch(`/api/conversations?sample=${sampleKey}`);
    const data = await res.json();
    state.conversations = data.conversations || [];
    state.totalCount = state.conversations.length;

    // Populate dropdown
    elements.convSelect.innerHTML = '';
    state.conversations.forEach((conv, idx) => {
      const opt = document.createElement('option');
      opt.value = conv.id;
      const statusIcon = conv.is_graded ? '✓' : '○';
      opt.textContent = `${statusIcon} #${idx + 1}: ${conv.id}`;
      elements.convSelect.appendChild(opt);
    });

    updateProgress();

    // Determine initial conversation to load (default to first conversation so filled scores are immediately visible)
    const targetId = selectId || state.conversations[0]?.id || null;

    if (targetId) {
      await loadConversation(targetId);
    }
  } catch (err) {
    showToast(`Failed to load conversation list: ${err.message}`, 'error');
  }
}

// Load a specific conversation by ID
async function loadConversation(annotationId) {
  try {
    const res = await fetch(`/api/conversation?sample=${state.currentSample}&id=${annotationId}`);
    if (!res.ok) {
      throw new Error(`Server returned ${res.status}`);
    }
    const data = await res.json();

    state.currentId = data.annotation_id;
    state.currentIndex = data.index;
    state.prevId = data.prev_id;
    state.nextId = data.next_id;

    // Update controls
    elements.convSelect.value = state.currentId;
    elements.convQuickJump.value = '';
    elements.btnPrev.disabled = !state.prevId;
    elements.btnNext.disabled = !state.nextId;

    // Render Conversation & Meta
    renderConversation(data);

    // Populate Scores Form
    populateScoresForm(data.saved_scores);

    // Scroll conversation to top
    document.querySelector('.conversation-pane').scrollTop = 0;
  } catch (err) {
    showToast(`Error loading conversation ${annotationId}: ${err.message}`, 'error');
  }
}

// Render Conversation Details & Turns
function renderConversation(data) {
  const rec = data.record || {};
  const conv = rec.conversation || {};
  const config = conv.config || {};

  // Target sheet info
  elements.gradingTargetSheet.textContent = data.sample_meta?.display_name || state.currentSample;

  // Header badges
  elements.metaAnnId.textContent = rec.annotation_id || '-';
  elements.metaDomain.textContent = conv.domain || 'General';
  elements.metaTopic.textContent = conv.topic || '-';

  if (data.is_graded) {
    elements.metaStatus.textContent = 'Graded in Excel';
    elements.metaStatus.className = 'badge badge-status is-graded';
    elements.gradingBadge.textContent = 'Saved';
    elements.gradingBadge.className = 'grading-badge is-graded';
  } else {
    elements.metaStatus.textContent = 'Pending Grading';
    elements.metaStatus.className = 'badge badge-status';
    elements.gradingBadge.textContent = 'Pending';
    elements.gradingBadge.className = 'grading-badge';
  }

  // Source File Relative Path & Index
  const src = rec.source || {};
  if (elements.metaSourcePath) {
    elements.metaSourcePath.textContent = src.relative_path || '-';
    elements.metaSourcePath.title = src.relative_path ? `Relative path: ${src.relative_path}` : 'No source path';
  }
  if (elements.metaSourceIndex) {
    elements.metaSourceIndex.textContent = `Index: ${src.index !== undefined ? src.index : '-'}`;
  }

  // Problem statement
  elements.metaProblem.textContent = conv.problem || 'No problem statement provided.';

  // Special Info (Disagreements or Profile Weakness)
  if (rec.disagreement_summary) {
    elements.specialInfoBox.style.display = 'block';
    elements.specialInfoBox.innerHTML = `<strong>⚠️ Judge Disagreement Diagnostic:</strong><br>${escapeHtml(rec.disagreement_summary)}`;
  } else if (rec.profile_categories && rec.profile_categories.length > 0) {
    elements.specialInfoBox.style.display = 'block';
    elements.specialInfoBox.innerHTML = `<strong>🎯 Metric Profile Category:</strong> ${rec.profile_categories.map(escapeHtml).join(', ')}`;
  } else {
    elements.specialInfoBox.style.display = 'none';
    elements.specialInfoBox.innerHTML = '';
  }

  // Simulation Config Grid
  elements.metaConfigGrid.innerHTML = '';
  if (src.relative_path) {
    const item = document.createElement('div');
    item.className = 'config-item';
    item.innerHTML = `
      <span class="config-k">Source File</span>
      <span class="config-v" style="font-family: monospace; font-size: 0.85em;">${escapeHtml(src.relative_path)}</span>
    `;
    elements.metaConfigGrid.appendChild(item);
  }
  if (src.index !== undefined) {
    const item = document.createElement('div');
    item.className = 'config-item';
    item.innerHTML = `
      <span class="config-k">Source Index</span>
      <span class="config-v">${escapeHtml(String(src.index))}</span>
    `;
    elements.metaConfigGrid.appendChild(item);
  }
  Object.entries(config).forEach(([k, v]) => {
    const item = document.createElement('div');
    item.className = 'config-item';
    item.innerHTML = `
      <span class="config-k">${escapeHtml(k.replace(/_/g, ' '))}</span>
      <span class="config-v">${escapeHtml(String(v))}</span>
    `;
    elements.metaConfigGrid.appendChild(item);
  });

  // Render Dialogue Turns
  elements.dialogueContainer.innerHTML = '';
  const turns = conv.conversation || [];
  turns.forEach((turn) => {
    const isStudent = (turn.speaker || '').toLowerCase() === 'student';
    const card = document.createElement('div');
    card.className = `turn-card ${isStudent ? 'turn-student' : 'turn-tutor'}`;

    const avatar = isStudent ? '👤' : '🤖';
    const speakerLabel = isStudent ? 'Student' : 'Tutor';
    const stateBadge = turn.state ? `<span class="turn-state-pill">${escapeHtml(turn.state)}</span>` : '';

    let contentHtml = '';
    if (isStudent) {
      contentHtml = `<div class="turn-content">${escapeHtml(turn.text || '')}</div>`;
    } else {
      contentHtml = `<div class="turn-content">${escapeHtml(turn.response || turn.text || '')}</div>`;
      if (turn.reasoning) {
        contentHtml += `
          <div class="turn-reasoning">
            <div class="reasoning-label">Tutor Reasoning:</div>
            <div>${escapeHtml(turn.reasoning)}</div>
          </div>
        `;
      }
    }

    card.innerHTML = `
      <div class="turn-avatar">${avatar}</div>
      <div class="turn-body">
        <div class="turn-meta">
          <span class="turn-speaker">${speakerLabel}</span>
          <span class="turn-num">Turn ${turn.turn || ''}</span>
          ${stateBadge}
        </div>
        ${contentHtml}
      </div>
    `;
    elements.dialogueContainer.appendChild(card);
  });

  applyFontSize();

  // Render LLM Judges Reference
  renderJudgeReference(rec);
}

// Render Judge reference drawer
function renderJudgeReference(record) {
  const llm = record.llm_judge_output || {};
  elements.judgeRefContent.innerHTML = '';

  const judgesFound = [];
  ['judge_1', 'judge_2', 'judge_3', 'judge_4'].forEach((jKey, idx) => {
    if (llm[jKey] && llm[jKey].evaluation) {
      judgesFound.push({ name: `Judge ${idx + 1} (${llm[jKey].model?.model_name || jKey})`, eval: llm[jKey].evaluation });
    }
  });

  if (judgesFound.length === 0) {
    elements.judgeRefContent.innerHTML = '<div class="text-muted">No individual judge logs embedded in this record.</div>';
    return;
  }

  judgesFound.forEach((j) => {
    const card = document.createElement('div');
    card.className = 'judge-card';

    const scoresList = [
      `Socratic: ${j.eval.socratic_guidance ?? '-'}`,
      `Scaffold: ${j.eval.scaffolding ?? '-'}`,
      `State: ${j.eval.state_adaptation ?? '-'}`,
      `Diag: ${j.eval.diagnosis ?? '-'}`,
      `Agency: ${j.eval.student_agency ?? '-'}`,
      `Prog: ${j.eval.progression ?? '-'}`,
      `Coher: ${j.eval.coherence ?? '-'}`,
      `Correct: ${j.eval.correctness ?? '-'}`,
    ].join(' | ');

    card.innerHTML = `
      <div class="judge-card-header">${escapeHtml(j.name)}</div>
      <div style="font-weight: 600; margin-bottom: 6px;">${escapeHtml(scoresList)}</div>
      <div style="font-size: 11px; color: var(--text-muted); line-height: 1.4;">
        ${j.eval.evidence ? Object.entries(j.eval.evidence).map(([m, ev]) => `<strong>${m}:</strong> ${escapeHtml(ev)}`).join('<br>') : ''}
      </div>
    `;
    elements.judgeRefContent.appendChild(card);
  });
}

// Populate scores form with existing data
function populateScoresForm(savedScores) {
  resetScoresForm();
  if (!savedScores) return;

  // Numeric metrics
  const numericMetrics = [
    'socratic_guidance',
    'scaffolding',
    'state_adaptation',
    'diagnosis',
    'student_agency',
    'progression',
    'coherence',
  ];

  numericMetrics.forEach((metric) => {
    const val = savedScores[metric];
    if (val !== null && val !== undefined) {
      state.scores[metric] = parseInt(val, 10);
      const group = document.querySelector(`.score-pills[data-field="${metric}"]`);
      if (group) {
        const pill = group.querySelector(`.pill[data-val="${val}"]`);
        if (pill) pill.classList.add('selected');
      }
    }
  });

  // Correctness
  if (savedScores.correctness !== null && savedScores.correctness !== undefined) {
    state.scores.correctness = Boolean(savedScores.correctness);
    const group = document.querySelector(`.bool-pills[data-field="correctness"]`);
    if (group) {
      const pill = group.querySelector(`.pill-bool[data-val="${savedScores.correctness}"]`);
      if (pill) pill.classList.add('selected');
    }
  }

  // Overall 5
  if (savedScores.overall_score_out_of_5 !== null && savedScores.overall_score_out_of_5 !== undefined) {
    elements.scoreOutOf5.value = savedScores.overall_score_out_of_5;
    state.scores.overall_score_out_of_5 = savedScores.overall_score_out_of_5;
  }

  // Overall 10
  if (savedScores.overall_score_out_of_10 !== null && savedScores.overall_score_out_of_10 !== undefined) {
    elements.scoreOutOf10.value = savedScores.overall_score_out_of_10;
    state.scores.overall_score_out_of_10 = savedScores.overall_score_out_of_10;
  }

  updateAllMetricHints();
}

// Reset form
function resetScoresForm(showFeedback = false) {
  state.scores = {
    socratic_guidance: null,
    scaffolding: null,
    state_adaptation: null,
    diagnosis: null,
    student_agency: null,
    progression: null,
    coherence: null,
    correctness: null,
    overall_score_out_of_5: null,
    overall_score_out_of_10: null,
  };

  document.querySelectorAll('.pill, .pill-bool').forEach((p) => p.classList.remove('selected'));
  elements.scoreOutOf5.value = '';
  elements.scoreOutOf10.value = '';

  updateAllMetricHints();

  if (showFeedback) {
    showToast('Form reset. Click Save (or Save & Next) to empty this row in Excel.', 'info');
  }
}

// Save Scores to Backend & Excel
async function saveScores(advanceToNext = true) {
  if (!state.currentId) return;

  const hasAny = Object.values(state.scores).some((v) => v !== null && v !== '');

  const payload = {
    sample_key: state.currentSample,
    annotation_id: state.currentId,
    scores: state.scores,
  };

  try {
    elements.btnSaveNext.disabled = true;
    elements.btnSaveOnly.disabled = true;

    const res = await fetch('/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || 'Failed to save scores');
    }

    showToast(`✓ ${data.message}`, 'success');

    // Update conversation item state in local memory and UI
    const isGraded = data.is_graded !== undefined ? data.is_graded : hasAny;
    const targetConv = state.conversations.find((c) => c.id === state.currentId);
    if (targetConv) targetConv.is_graded = isGraded;

    // Update dropdown option label
    const opt = elements.convSelect.querySelector(`option[value="${state.currentId}"]`);
    if (opt) {
      const statusIcon = isGraded ? '✓' : '○';
      opt.textContent = `${statusIcon} #${state.currentIndex}: ${state.currentId}`;
    }

    if (isGraded) {
      elements.metaStatus.textContent = 'Graded in Excel';
      elements.metaStatus.className = 'badge badge-status is-graded';
      elements.gradingBadge.textContent = 'Saved';
      elements.gradingBadge.className = 'grading-badge is-graded';
    } else {
      elements.metaStatus.textContent = 'Pending Grading';
      elements.metaStatus.className = 'badge badge-status';
      elements.gradingBadge.textContent = 'Ungraded';
      elements.gradingBadge.className = 'grading-badge';
    }

    updateProgress();

    // Refresh sample tabs summary count
    updateTabCount(state.currentSample, data.summary);

    if (advanceToNext && data.next_id) {
      await loadConversation(data.next_id);
    }
  } catch (err) {
    showToast(`Save failed: ${err.message}`, 'error');
  } finally {
    elements.btnSaveNext.disabled = false;
    elements.btnSaveOnly.disabled = false;
  }
}

// Quick jump handler (by index or by ID)
function handleQuickJump() {
  const query = elements.convQuickJump.value.trim().toUpperCase();
  if (!query) return;

  // If query is an index number (e.g. "1" or "25")
  if (/^\d+$/.test(query)) {
    const idx = parseInt(query, 10);
    if (idx >= 1 && idx <= state.conversations.length) {
      const targetId = state.conversations[idx - 1].id;
      loadConversation(targetId);
      return;
    }
  }

  // If query is ID prefix or partial match
  const match = state.conversations.find(
    (c) => c.id.toUpperCase() === query || c.id.toUpperCase().endsWith(`-${query}`)
  );
  if (match) {
    loadConversation(match.id);
  } else {
    showToast(`No conversation found matching "${query}"`, 'error');
  }
}

// Jump to next unannotated conversation
function jumpToNextUngraded() {
  const unannotated = state.conversations.find((c) => !c.is_graded);
  if (unannotated) {
    loadConversation(unannotated.id);
  } else {
    showToast('🎉 All conversations in this set are graded!', 'success');
  }
}

// Progress calculation
function updateProgress() {
  const total = state.conversations.length;
  const graded = state.conversations.filter((c) => c.is_graded).length;
  const pct = total > 0 ? Math.round((graded / total) * 100) : 0;

  elements.progressCount.textContent = `${graded} / ${total}`;
  elements.progressPct.textContent = `(${pct}%)`;
  elements.progressFill.style.width = `${pct}%`;
}

function updateTabCount(sampleKey, summary) {
  if (!summary) return;
  const tabBtn = document.querySelector(`.tab-btn[data-sample="${sampleKey}"]`);
  if (tabBtn) {
    const meta = sampleKey.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
    tabBtn.innerHTML = `${meta} <span style="opacity: 0.8; font-size: 11px;">(${summary.graded}/${summary.total})</span>`;
  }
}

const ALL_METRIC_KEYS = [
  'socratic_guidance',
  'scaffolding',
  'state_adaptation',
  'diagnosis',
  'student_agency',
  'progression',
  'coherence',
  'correctness',
];

// Initialize Rubric Data & build inline guides
async function initRubricData() {
  if (!state.rubricData) {
    try {
      const res = await fetch('/api/rubric');
      const data = await res.json();
      state.rubricData = data.rubric || {};
      buildInlineRubricGuides();
    } catch (err) {
      console.error('Failed to load rubric data:', err);
    }
  }
}

function buildInlineRubricGuides() {
  if (!state.rubricData) return;

  // 1. Populate individual inline guide cards
  ALL_METRIC_KEYS.forEach((key) => {
    const item = state.rubricData[key];
    const box = document.getElementById(`guide-${key}`);
    if (box && item) {
      const ruleHtml = item.rule
        ? `<div class="guide-rule-alert"><strong>⚠️ Critical Rule (judge_prompt.md):</strong> ${escapeHtml(item.rule)}</div>`
        : '';
      let levelsHtml = '';
      if (item.levels) {
        levelsHtml = `
          <div class="guide-levels-grid">
            ${Object.entries(item.levels)
              .map(([lvl, desc]) => `<div class="guide-level-item"><strong>[${lvl}]</strong> ${escapeHtml(desc)}</div>`)
              .join('')}
          </div>
        `;
      }
      box.innerHTML = `
        <div class="guide-desc"><strong>What to evaluate:</strong> ${escapeHtml(item.description)}</div>
        ${ruleHtml}
        ${levelsHtml}
      `;
    }
  });

  // 2. Populate Complete Cheat Sheet Drawer
  const cheatBody = document.getElementById('rubric-cheat-body');
  if (cheatBody) {
    cheatBody.innerHTML = '';
    Object.entries(state.rubricData).forEach(([metricKey, item]) => {
      const card = document.createElement('div');
      card.className = 'rubric-item';
      const ruleHtml = item.rule
        ? `<div class="guide-rule-alert" style="margin: 6px 0;"><strong>⚠️ Evaluation Rule:</strong> ${escapeHtml(item.rule)}</div>`
        : '';
      let levelsHtml = '';
      if (item.levels) {
        levelsHtml = `
          <div class="guide-levels-grid">
            ${Object.entries(item.levels)
              .map(([lvl, desc]) => `<div class="guide-level-item"><strong>[${lvl}]</strong> ${escapeHtml(desc)}</div>`)
              .join('')}
          </div>
        `;
      }
      card.innerHTML = `
        <div class="rubric-item-title">${escapeHtml(item.title)}</div>
        <div class="rubric-item-desc">${escapeHtml(item.description)}</div>
        ${ruleHtml}
        ${levelsHtml}
      `;
      cheatBody.appendChild(card);
    });
  }
}

// Update the live hint text below each metric row
function updateMetricHint(metric, val = null) {
  const hintEl = document.getElementById(`hint-${metric}`);
  if (!hintEl) return;

  const activeVal = val !== null ? val : state.scores[metric];
  if (activeVal === null || activeVal === undefined || !state.rubricData || !state.rubricData[metric]) {
    hintEl.textContent = 'Hover or click a score for rubric criteria';
    hintEl.classList.remove('highlighted');
    return;
  }

  const levels = state.rubricData[metric].levels || {};
  let lvlText = levels[String(activeVal)];
  if (!lvlText && typeof activeVal === 'boolean') {
    lvlText = levels[activeVal ? 'TRUE' : 'FALSE'];
  }

  if (lvlText) {
    hintEl.textContent = lvlText;
    hintEl.classList.add('highlighted');
  } else {
    hintEl.textContent = `Selected: ${activeVal}`;
    hintEl.classList.remove('highlighted');
  }
}

function updateAllMetricHints() {
  ALL_METRIC_KEYS.forEach((m) => updateMetricHint(m));
}

// Rubric Modal display
async function openRubricModal() {
  await initRubricData();

  elements.rubricModalContent.innerHTML = '';
  Object.entries(state.rubricData).forEach(([k, item]) => {
    const div = document.createElement('div');
    div.className = 'rubric-item';

    const ruleHtml = item.rule
      ? `<div class="guide-rule-alert" style="margin: 6px 0 10px 0;"><strong>⚠️ Critical Rule (judge_prompt.md):</strong> ${escapeHtml(item.rule)}</div>`
      : '';

    let levelsHtml = '';
    if (item.levels) {
      levelsHtml = `
        <div class="rubric-levels">
          ${Object.entries(item.levels)
            .map(([lvl, desc]) => `<div class="rubric-level"><strong>Level ${lvl}:</strong> ${escapeHtml(desc)}</div>`)
            .join('')}
        </div>
      `;
    }

    div.innerHTML = `
      <div class="rubric-item-title">${escapeHtml(item.title)}</div>
      <div class="rubric-item-desc">${escapeHtml(item.description)}</div>
      ${ruleHtml}
      ${levelsHtml}
    `;
    elements.rubricModalContent.appendChild(div);
  });

  elements.rubricModal.style.display = 'flex';
}

function closeRubricModal() {
  elements.rubricModal.style.display = 'none';
}

// Toast notification
let toastTimer = null;
function showToast(message, type = 'info') {
  if (toastTimer) clearTimeout(toastTimer);

  elements.toastBanner.textContent = message;
  elements.toastBanner.className = `toast show ${type === 'success' ? 'toast-success' : type === 'error' ? 'toast-error' : ''}`;

  toastTimer = setTimeout(() => {
    elements.toastBanner.classList.remove('show');
  }, 3500);
}

// Utility: escape HTML
function escapeHtml(text) {
  if (text === null || text === undefined) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
