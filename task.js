"use strict";

const LIST_IDS = ["A", "B", "C", "D"];
const UINT_32 = 4294967296;
const TEST_RESPONSE_TIMEOUT_MS = 30000;
const TEST_REPLAY_ALLOWED = false;
const PRACTICE_WORDS = [
  { listWordId: 901, objectId: 901, word: "nupa", ttsText: "noo-pah", contrast: "practice", contrastGroup: "", phonology: "practice" },
  { listWordId: 902, objectId: 902, word: "teebo", ttsText: "tee-boh", contrast: "practice", contrastGroup: "", phonology: "practice" },
  { listWordId: 903, objectId: 903, word: "moga", ttsText: "moh-gah", contrast: "practice", contrastGroup: "", phonology: "practice" },
  { listWordId: 904, objectId: 904, word: "safee", ttsText: "sah-fee", contrast: "practice", contrastGroup: "", phonology: "practice" },
  { listWordId: 905, objectId: 905, word: "looma", ttsText: "loo-mah", contrast: "practice", contrastGroup: "", phonology: "practice" },
];

const state = {
  config: null,
  listsPayload: null,
  participantId: "",
  seed: 0,
  seedHex: "",
  listId: "",
  listOverride: null,
  words: [],
  wordByPairId: new Map(),
  wordByObjectId: new Map(),
  schedule: null,
  sessionStartedAt: "",
  sessionCompletedAt: "",
  encounterCounts: new Map(),
  previousByWord: new Map(),
  learningEvents: [],
  learningTrials: [],
  practiceEvents: [],
  testData: [],
  eventSeq: 0,
  totalTrials: 0,
  completedTrials: 0,
};

const els = {};

document.addEventListener("DOMContentLoaded", init);

async function init() {
  cacheElements();
  bindStaticEvents();

  if (!isSupportedChrome()) {
    showUnsupportedBrowser();
    return;
  }

  setSetupStatus("刺激リストを読み込んでいます。");

  try {
    const [config, listsPayload] = await Promise.all([
      loadJson("config/task_design_plan2.json"),
      loadJson("stimuli/participant_lists_plan2.json"),
    ]);
    state.config = config;
    state.listsPayload = listsPayload;
    setSetupStatus("準備完了");
    els.startButton.disabled = false;
  } catch (error) {
    setSetupStatus(
      "読み込みに失敗しました。ローカルサーバーから index.html を開いてください。",
      true,
    );
    els.startButton.disabled = true;
    console.error(error);
  }
}

function cacheElements() {
  for (const id of [
    "setupScreen",
    "setupForm",
    "participantId",
    "listOverride",
    "startButton",
    "setupStatus",
    "taskScreen",
    "phaseLabel",
    "taskTitle",
    "progressText",
    "progressBar",
    "messagePanel",
    "messageTitle",
    "messageBody",
    "continueButton",
    "secondaryButton",
    "trialPanel",
    "trialCueText",
    "replayButton",
    "objectGrid",
    "finishScreen",
    "summaryBox",
    "downloadXlsxButton",
  ]) {
    els[id] = document.getElementById(id);
  }
}

function bindStaticEvents() {
  els.startButton.disabled = true;
  els.setupForm.addEventListener("submit", handleStart);
  els.downloadXlsxButton.addEventListener("click", downloadWorkbookXlsx);
}

async function handleStart(event) {
  event.preventDefault();
  const participantId = els.participantId.value.trim();
  if (!participantId) {
    setSetupStatus("参加者IDを入力してください。", true);
    return;
  }

  els.startButton.disabled = true;
  setSetupStatus("スケジュールを作成しています。");

  try {
    await prepareParticipant(participantId, els.listOverride.value || null);
    els.setupScreen.classList.add("hidden");
    els.taskScreen.classList.remove("hidden");
    await runExperiment();
  } catch (error) {
    console.error(error);
    showFatalError(error);
  }
}

async function prepareParticipant(participantId, listOverride) {
  const seedInfo = await stableSeed(participantId);
  const listId = listOverride || assignList(seedInfo.seed);
  if (!LIST_IDS.includes(listId)) {
    throw new Error(`Unknown list ID: ${listId}`);
  }

  state.participantId = participantId;
  state.seed = seedInfo.seed;
  state.seedHex = seedInfo.hex;
  state.listId = listId;
  state.listOverride = listOverride;

  const words = normalizeRows(state.listsPayload.lists[listId]);
  const schedule = buildSchedule(participantId, seedInfo.seed, listId, words);

  state.words = words;
  state.wordByPairId = new Map(words.map((row) => [row.listWordId, row]));
  state.wordByObjectId = new Map(words.map((row) => [row.objectId, row]));
  state.schedule = schedule;
  state.sessionStartedAt = new Date().toISOString();
  state.sessionCompletedAt = "";
  state.encounterCounts = new Map();
  state.previousByWord = new Map();
  state.learningEvents = [];
  state.learningTrials = [];
  state.practiceEvents = [];
  state.testData = [];
  state.eventSeq = 0;
  state.completedTrials = 0;
  state.totalTrials =
    schedule.learningBlocks.reduce((sum, block) => sum + block.trials.length, 0)
    + schedule.testBlocks.reduce((sum, block) => sum + block.trials.length, 0);
}

async function runExperiment() {
  updateProgress("待機", "準備", 0, state.totalTrials);

  await runVolumeCheck();
  await runTutorial();

  for (let block = 1; block <= state.config.learning.blocks; block += 1) {
    await showGate(
      `ブロック ${block}: 学習`,
      "音声を聞き、対応する絵を選択してください。",
      "学習を開始",
    );

    const learningBlock = state.schedule.learningBlocks[block - 1];
    for (const trial of learningBlock.trials) {
      await runLearningTrial(trial);
      state.completedTrials += 1;
      updateProgress("学習", `ブロック ${block}`, state.completedTrials, state.totalTrials);
    }

    await showGate(
      `ブロック ${block}: 5AFC`,
      "音声に対応する絵を選択してください。",
      "5AFCを開始",
    );

    const testBlock = state.schedule.testBlocks[block - 1];
    for (const trial of testBlock.trials) {
      await runTestTrial(trial);
      state.completedTrials += 1;
      updateProgress("5AFC", `ブロック ${block}`, state.completedTrials, state.totalTrials);
    }
  }

  finishExperiment();
}

async function runVolumeCheck() {
  updateProgress("音量", "音量チェック", 0, state.totalTrials);
  els.trialPanel.classList.add("hidden");
  els.messagePanel.classList.remove("hidden");
  els.continueButton.classList.remove("hidden");
  els.secondaryButton.classList.add("hidden");
  els.messageTitle.textContent = "音量チェック";
  els.messageBody.textContent = "音声を再生します。聞こえたらそのまま進んでください。聞こえない場合は、端末やブラウザの音量を調整してからもう一度再生してください。";
  els.continueButton.textContent = "音声を再生";
  els.taskTitle.textContent = "音量チェック";

  let playCount = 0;
  return new Promise((resolve) => {
    const cleanup = () => {
      els.continueButton.removeEventListener("click", onPrimary);
      els.secondaryButton.removeEventListener("click", onReplay);
      els.secondaryButton.classList.add("hidden");
      els.messagePanel.classList.add("hidden");
      els.trialPanel.classList.remove("hidden");
    };

    const playAudio = async () => {
      els.continueButton.disabled = true;
      els.secondaryButton.disabled = true;
      const startedAtMs = performance.now();
      const audioResult = await playWord(PRACTICE_WORDS[0]);
      playCount += 1;
      state.practiceEvents.push({
        participantId: state.participantId,
        phase: "volume_check",
        practiceEvent: state.practiceEvents.length + 1,
        word: PRACTICE_WORDS[0].word,
        playCount,
        audioSource: audioResult.audioSource,
        audioPlayOk: audioResult.audioPlayOk,
        startedAtMs: roundMs(startedAtMs),
        endedAtMs: roundMs(performance.now()),
      });
      els.messageBody.textContent = "音声が聞こえた場合は続けてください。聞こえない場合は音量を調整し、もう一度再生してください。";
      els.continueButton.textContent = "聞こえたので続ける";
      els.continueButton.disabled = false;
      els.secondaryButton.textContent = "もう一度再生";
      els.secondaryButton.disabled = false;
      els.secondaryButton.classList.remove("hidden");
    };

    const onPrimary = async () => {
      if (playCount === 0) {
        await playAudio();
        return;
      }
      cleanup();
      resolve();
    };

    const onReplay = async () => {
      await playAudio();
    };

    els.continueButton.addEventListener("click", onPrimary);
    els.secondaryButton.addEventListener("click", onReplay);
  });
}

async function runTutorial() {
  updateProgress("練習", "説明", 0, state.totalTrials);
  await showGate(
    "説明",
    "音声が1つずつ流れます。画面の絵の中から、対応すると思う絵をクリックしてください。学習では3つの絵、テストでは5つの絵から選びます。",
    "練習を開始",
  );

  await runPracticeLearningTrial();

  await showGate(
    "練習: 5AFC",
    "次は5つの絵から1つを選ぶ練習です。本番でも同じようにクリックで回答します。",
    "練習テストを開始",
  );

  await runPracticeTestTrial();

  await showGate(
    "本番",
    "ここから本番です。正解・不正解の表示はありません。できるだけ集中して選択してください。",
    "本番を開始",
  );
}

async function runPracticeLearningTrial() {
  const practiceObjects = PRACTICE_WORDS.slice(0, 3);
  renderTrialObjects("learning", practiceObjects.map((row) => row.objectId));
  setCueText("練習");

  for (let index = 0; index < practiceObjects.length; index += 1) {
    const word = practiceObjects[index];
    setCueText(`練習 ${index + 1} / ${practiceObjects.length}`);
    setObjectButtonsEnabled(false);
    clearSelectedObjects();
    const audioResult = await playWord(word);
    const responseWindowStartMs = performance.now();
    setObjectButtonsEnabled(true);
    const response = await waitForObjectChoice(practiceObjects.map((row) => row.objectId), { allowKeyboard: true });
    const respondedAtMs = performance.now();
    const correct = response.objectId === word.objectId;
    markSelectedObject(response.objectId);
    setObjectButtonsEnabled(false);
    state.practiceEvents.push({
      participantId: state.participantId,
      phase: "practice_learning",
      practiceEvent: state.practiceEvents.length + 1,
      word: word.word,
      targetObjectId: word.objectId,
      optionObjectIds: practiceObjects.map((row) => row.objectId),
      responseObjectId: response.objectId,
      responsePosition: response.position,
      responseSource: response.source,
      responseClientX: response.clientX,
      responseClientY: response.clientY,
      correct,
      rtMs: Math.round(respondedAtMs - responseWindowStartMs),
      audioSource: audioResult.audioSource,
      audioPlayOk: audioResult.audioPlayOk,
    });
    await sleep(260);
  }
}

async function runPracticeTestTrial() {
  const target = PRACTICE_WORDS[1];
  const options = PRACTICE_WORDS.map((row) => row.objectId);
  renderTrialObjects("test", options);
  setCueText("練習テスト");
  setObjectButtonsEnabled(false);
  clearSelectedObjects();
  const audioResult = await playWord(target);
  const responseWindowStartMs = performance.now();
  setObjectButtonsEnabled(true);
  const response = await waitForObjectChoice(options, {
    allowKeyboard: false,
    timeoutMs: TEST_RESPONSE_TIMEOUT_MS,
  });
  const respondedAtMs = performance.now();
  const correct = response.objectId !== null && response.objectId === target.objectId;
  if (response.objectId !== null) {
    markSelectedObject(response.objectId);
  } else {
    setCueText("時間切れ");
  }
  setObjectButtonsEnabled(false);
  state.practiceEvents.push({
    participantId: state.participantId,
    phase: "practice_5afc",
    practiceEvent: state.practiceEvents.length + 1,
    word: target.word,
    targetObjectId: target.objectId,
    optionObjectIds: options,
    responseObjectId: response.objectId,
    responsePosition: response.position,
    responseSource: response.source,
    responseClientX: response.clientX,
    responseClientY: response.clientY,
    responseTimedOut: response.timedOut,
    noResponse: response.noResponse,
    correct,
    rtMs: Math.round(respondedAtMs - responseWindowStartMs),
    responseTimeoutMs: TEST_RESPONSE_TIMEOUT_MS,
    audioSource: audioResult.audioSource,
    audioPlayOk: audioResult.audioPlayOk,
  });
  await sleep(400);
}

async function runLearningTrial(trial) {
  updateProgress("学習", `ブロック ${trial.block}`, state.completedTrials, state.totalTrials);
  renderTrialObjects("learning", trial.objectIds);

  const trialStartedAtMs = performance.now();
  const eventIds = [];

  for (let index = 0; index < trial.wordOrderPairIds.length; index += 1) {
    const pairId = trial.wordOrderPairIds[index];
    const word = getWord(pairId);
    const contextObjectIds = trial.objectIds.slice();
    const targetPosition = contextObjectIds.indexOf(word.objectId) + 1;
    const previous = state.previousByWord.get(pairId) || null;
    const encounterIndex = (state.encounterCounts.get(pairId) || 0) + 1;
    state.encounterCounts.set(pairId, encounterIndex);

    setCueText(`音声 ${index + 1} / ${trial.wordOrderPairIds.length}`);
    setObjectButtonsEnabled(false);
    clearSelectedObjects();

    const audioResult = await playWord(word);
    const responseWindowStartMs = performance.now();
    setObjectButtonsEnabled(true);

    const response = await waitForObjectChoice(contextObjectIds, { allowKeyboard: true });
    const respondedAtMs = performance.now();
    const correct = response.objectId === word.objectId;
    markSelectedObject(response.objectId);
    setObjectButtonsEnabled(false);

    const eventSeq = state.eventSeq + 1;
    state.eventSeq = eventSeq;
    eventIds.push(eventSeq);

    const row = {
      participantId: state.participantId,
      seed: state.seed,
      seedHex12: state.seedHex.slice(0, 12),
      listId: state.listId,
      phase: "learning",
      block: trial.block,
      blockTrial: trial.blockTrial,
      wordEventInTrial: index + 1,
      eventSeq,
      pairId,
      word: word.word,
      ttsText: word.ttsText,
      targetObjectId: word.objectId,
      contrast: word.contrast,
      contrastGroup: word.contrastGroup,
      phonology: word.phonology,
      syllableCount: word.syllableCount,
      syllableTemplate: word.syllableTemplate,
      phones: word.phones,
      ipaTarget: word.ipaTarget,
      phonologicalNeighborhoodSize: word.phonologicalNeighborhoodSize,
      nearestRealWordDistance: word.nearestRealWordDistance,
      nearestRealWords: word.nearestRealWords,
      encounterIndex,
      contextPairIds: trial.pairIds,
      contextObjectIds,
      wordOrderPairIds: trial.wordOrderPairIds,
      targetPosition,
      responseObjectId: response.objectId,
      responsePosition: response.position,
      responseSource: response.source,
      responseClientX: response.clientX,
      responseClientY: response.clientY,
      correct,
      rtMs: Math.round(respondedAtMs - responseWindowStartMs),
      previousResponseObjectId: previous ? previous.responseObjectId : null,
      previousCorrect: previous ? previous.correct : null,
      previousRtMs: previous ? previous.rtMs : null,
      audioSource: audioResult.audioSource,
      audioPlayOk: audioResult.audioPlayOk,
      audioStartedAtMs: audioResult.startedAtMs,
      audioEndedAtMs: audioResult.endedAtMs,
      responseWindowStartMs: roundMs(responseWindowStartMs),
      respondedAtMs: roundMs(respondedAtMs),
    };

    state.learningEvents.push(row);
    state.previousByWord.set(pairId, {
      encounterIndex,
      responseObjectId: response.objectId,
      responsePosition: response.position,
      correct,
      rtMs: row.rtMs,
    });

    await sleep(180);
  }

  state.learningTrials.push({
    participantId: state.participantId,
    seed: state.seed,
    listId: state.listId,
    phase: "learning_trial",
    block: trial.block,
    blockTrial: trial.blockTrial,
    pairIds: trial.pairIds,
    objectIds: trial.objectIds,
    wordOrderPairIds: trial.wordOrderPairIds,
    eventSeqs: eventIds,
    trialStartedAtMs: roundMs(trialStartedAtMs),
    trialEndedAtMs: roundMs(performance.now()),
  });
}

async function runTestTrial(trial) {
  updateProgress("5AFC", `ブロック ${trial.block}`, state.completedTrials, state.totalTrials);
  renderTrialObjects("test", trial.optionObjectIds);

  const target = getWord(trial.targetPairId);
  let replayCount = 0;
  setCueText("音声");
  setObjectButtonsEnabled(false);
  clearSelectedObjects();
  els.replayButton.classList.add("hidden");
  els.replayButton.disabled = true;

  const firstAudioResult = await playWord(target);
  const responseWindowStartMs = performance.now();

  if (TEST_REPLAY_ALLOWED) {
    els.replayButton.onclick = async () => {
      replayCount += 1;
      els.replayButton.disabled = true;
      await playWord(target);
      els.replayButton.disabled = false;
    };
    els.replayButton.disabled = false;
    els.replayButton.classList.remove("hidden");
  }

  setCueText("選択");
  setObjectButtonsEnabled(true);
  const response = await waitForObjectChoice(trial.optionObjectIds, {
    allowKeyboard: false,
    timeoutMs: TEST_RESPONSE_TIMEOUT_MS,
  });
  const respondedAtMs = performance.now();
  const correct = response.objectId !== null && response.objectId === trial.targetObjectId;

  if (response.objectId !== null) {
    markSelectedObject(response.objectId);
  } else {
    setCueText("時間切れ");
  }
  setObjectButtonsEnabled(false);
  els.replayButton.disabled = true;
  els.replayButton.classList.add("hidden");
  els.replayButton.onclick = null;

  state.testData.push({
    participantId: state.participantId,
    seed: state.seed,
    seedHex12: state.seedHex.slice(0, 12),
    listId: state.listId,
    phase: "test_5afc",
    block: trial.block,
    blockTrial: trial.blockTrial,
    targetPairId: trial.targetPairId,
    targetWord: trial.targetWord,
    ttsText: target.ttsText,
    targetObjectId: trial.targetObjectId,
    contrast: target.contrast,
    contrastGroup: target.contrastGroup,
    phonology: target.phonology,
    syllableCount: target.syllableCount,
    syllableTemplate: target.syllableTemplate,
    phones: target.phones,
    ipaTarget: target.ipaTarget,
    phonologicalNeighborhoodSize: target.phonologicalNeighborhoodSize,
    nearestRealWordDistance: target.nearestRealWordDistance,
    nearestRealWords: target.nearestRealWords,
    encountersCompletedForWord: state.encounterCounts.get(trial.targetPairId) || null,
    optionPairIds: trial.optionPairIds,
    optionObjectIds: trial.optionObjectIds,
    targetPosition: trial.targetPosition,
    responseObjectId: response.objectId,
    responsePosition: response.position,
    responseSource: response.source,
    responseClientX: response.clientX,
    responseClientY: response.clientY,
    responseTimedOut: response.timedOut,
    noResponse: response.noResponse,
    correct,
    rtMs: Math.round(respondedAtMs - responseWindowStartMs),
    responseTimeoutMs: TEST_RESPONSE_TIMEOUT_MS,
    replayAllowed: TEST_REPLAY_ALLOWED,
    replayCount,
    audioSource: firstAudioResult.audioSource,
    audioPlayOk: firstAudioResult.audioPlayOk,
    audioStartedAtMs: firstAudioResult.startedAtMs,
    audioEndedAtMs: firstAudioResult.endedAtMs,
    responseWindowStartMs: roundMs(responseWindowStartMs),
    respondedAtMs: roundMs(respondedAtMs),
  });

  await sleep(180);
}

function finishExperiment() {
  state.sessionCompletedAt = new Date().toISOString();
  els.taskScreen.classList.add("hidden");
  els.finishScreen.classList.remove("hidden");

  els.summaryBox.innerHTML = [
    `<strong>参加者ID:</strong> ${escapeHtml(state.participantId)}`,
    `<strong>リスト:</strong> ${state.listId}`,
    `<strong>保存ファイル:</strong> ${escapeHtml(exportFilename("xlsx"))}`,
  ].join("<br>");
  window.setTimeout(downloadWorkbookXlsx, 250);
}

function showFatalError(error) {
  els.setupScreen.classList.add("hidden");
  els.taskScreen.classList.remove("hidden");
  els.finishScreen.classList.add("hidden");
  els.trialPanel.classList.add("hidden");
  els.messagePanel.classList.remove("hidden");
  els.phaseLabel.textContent = "エラー";
  els.taskTitle.textContent = "停止";
  els.messageTitle.textContent = "実行できません";
  els.messageBody.textContent = error && error.message ? error.message : String(error);
  els.continueButton.classList.add("hidden");
  els.secondaryButton.classList.add("hidden");
}

function showGate(title, body, buttonText) {
  els.trialPanel.classList.add("hidden");
  els.messagePanel.classList.remove("hidden");
  els.continueButton.classList.remove("hidden");
  els.secondaryButton.classList.add("hidden");
  els.continueButton.disabled = false;
  els.messageTitle.textContent = title;
  els.messageBody.textContent = body;
  els.continueButton.textContent = buttonText;
  els.taskTitle.textContent = title;
  return new Promise((resolve) => {
    const onClick = () => {
      els.continueButton.removeEventListener("click", onClick);
      els.messagePanel.classList.add("hidden");
      els.trialPanel.classList.remove("hidden");
      resolve();
    };
    els.continueButton.addEventListener("click", onClick);
  });
}

function renderTrialObjects(mode, objectIds) {
  els.objectGrid.innerHTML = "";
  els.objectGrid.className = `object-grid ${mode}`;
  els.trialPanel.classList.remove("hidden");

  objectIds.forEach((objectId, index) => {
    const button = document.createElement("button");
    button.className = "object-card";
    button.type = "button";
    button.dataset.objectId = String(objectId);
    button.dataset.position = String(index + 1);
    button.setAttribute("aria-label", `選択肢 ${index + 1}`);
    button.innerHTML = `
      <span class="object-art" aria-hidden="true">
        <img src="${objectImagePath(objectId)}" alt="" onerror="this.replaceWith(svgFallbackForObject(${Number(objectId)}));">
      </span>
    `;
    els.objectGrid.appendChild(button);
  });
}

function setCueText(text) {
  els.trialCueText.textContent = text;
}

function setObjectButtonsEnabled(enabled) {
  for (const button of els.objectGrid.querySelectorAll(".object-card")) {
    button.disabled = !enabled;
  }
}

function clearSelectedObjects() {
  for (const button of els.objectGrid.querySelectorAll(".object-card")) {
    button.classList.remove("selected");
  }
}

function markSelectedObject(objectId) {
  clearSelectedObjects();
  const target = els.objectGrid.querySelector(`.object-card[data-object-id="${objectId}"]`);
  if (target) {
    target.classList.add("selected");
  }
}

function waitForObjectChoice(validObjectIds, options) {
  const buttons = Array.from(els.objectGrid.querySelectorAll(".object-card"));
  const valid = new Set(validObjectIds.map(Number));

  return new Promise((resolve) => {
    let timeoutId = null;
    const cleanup = () => {
      for (const button of buttons) {
        button.removeEventListener("click", onClick);
      }
      document.removeEventListener("keydown", onKeyDown);
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };

    const choose = (button, source, event = null) => {
      if (!button || button.disabled) {
        return;
      }
      const objectId = Number(button.dataset.objectId);
      if (!valid.has(objectId)) {
        return;
      }
      cleanup();
      resolve({
        objectId,
        position: Number(button.dataset.position),
        source,
        clientX: event ? Math.round(event.clientX) : null,
        clientY: event ? Math.round(event.clientY) : null,
        timedOut: false,
        noResponse: false,
      });
    };

    const onClick = (event) => choose(event.currentTarget, "click", event);

    const onKeyDown = (event) => {
      if (!options.allowKeyboard || !/^[1-9]$/.test(event.key)) {
        return;
      }
      const index = Number(event.key) - 1;
      choose(buttons[index], "keyboard");
    };

    for (const button of buttons) {
      button.addEventListener("click", onClick);
    }
    document.addEventListener("keydown", onKeyDown);

    if (Number.isFinite(options.timeoutMs) && options.timeoutMs > 0) {
      timeoutId = window.setTimeout(() => {
        cleanup();
        resolve({
          objectId: null,
          position: null,
          source: "timeout",
          clientX: null,
          clientY: null,
          timedOut: true,
          noResponse: true,
        });
      }, options.timeoutMs);
    }
  });
}

async function playWord(word) {
  const audioStartedAtMs = roundMs(performance.now());
  const fileResult = await tryAudioFile(word);
  if (fileResult.audioPlayOk) {
    return {
      ...fileResult,
      startedAtMs: audioStartedAtMs,
      endedAtMs: roundMs(performance.now()),
    };
  }

  const speechResult = await speakOrSilent(word);
  return {
    ...speechResult,
    startedAtMs: audioStartedAtMs,
    endedAtMs: roundMs(performance.now()),
  };
}

async function tryAudioFile(word) {
  const url = `audio/${encodeURIComponent(word.word)}.mp3`;
  try {
    const response = await fetch(url, { method: "HEAD", cache: "no-store" });
    if (!response.ok) {
      return { audioSource: "missing_mp3", audioPlayOk: false };
    }
  } catch (_error) {
    return { audioSource: "missing_mp3", audioPlayOk: false };
  }

  return new Promise((resolve) => {
    const audio = new Audio(url);
    let settled = false;

    const finish = (ok, source) => {
      if (settled) {
        return;
      }
      settled = true;
      window.clearTimeout(timeout);
      audio.pause();
      resolve({ audioSource: source, audioPlayOk: ok });
    };

    const timeout = window.setTimeout(() => finish(false, "mp3_timeout"), 4000);

    audio.addEventListener("ended", () => finish(true, "mp3"));
    audio.addEventListener("error", () => finish(false, "mp3_error"));
    try {
      const playPromise = audio.play();
      if (playPromise) {
        playPromise.catch(() => finish(false, "mp3_blocked"));
      }
    } catch (_error) {
      finish(false, "mp3_blocked");
    }
  });
}

function speakOrSilent(word) {
  const text = word.ttsText || word.word;
  const estimatedMs = Math.max(650, Math.min(1800, text.length * 95 + 360));

  if (!("speechSynthesis" in window) || typeof SpeechSynthesisUtterance === "undefined") {
    return sleep(estimatedMs).then(() => ({ audioSource: "silent_fallback", audioPlayOk: false }));
  }

  return new Promise((resolve) => {
    let settled = false;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    utterance.rate = 0.78;
    utterance.pitch = 1;

    const timeout = window.setTimeout(() => {
      window.speechSynthesis.cancel();
      finish(false, "speechSynthesis_timeout");
    }, estimatedMs + 1200);

    const finish = (ok, source) => {
      if (settled) {
        return;
      }
      settled = true;
      window.clearTimeout(timeout);
      resolve({ audioSource: source, audioPlayOk: ok });
    };

    utterance.onend = () => finish(true, "speechSynthesis");
    utterance.onerror = () => finish(false, "speechSynthesis_error");
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  });
}

async function loadJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} could not be loaded (${response.status})`);
  }
  return response.json();
}

async function stableSeed(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  const bytes = Array.from(new Uint8Array(digest));
  const hex = bytes.map((byte) => byte.toString(16).padStart(2, "0")).join("");
  return {
    seed: Number.parseInt(hex.slice(0, 12), 16),
    hex,
  };
}

function assignList(seed) {
  return LIST_IDS[seed % LIST_IDS.length];
}

function normalizeRows(rows) {
  if (!Array.isArray(rows) || rows.length !== 20) {
    throw new Error("Participant list must contain 20 words.");
  }
  return rows.map((row) => ({
    ...row,
    listWordId: Number(row.listWordId),
    objectId: Number(row.objectId),
    syllableCount: Number(row.syllableCount),
    phonologicalNeighborhoodSize: Number(row.phonologicalNeighborhoodSize),
    nearestRealWordDistance: Number(row.nearestRealWordDistance),
  }));
}

function buildSchedule(participantId, seed, listId, words) {
  const rng = createRng(seed);
  const learningBlocks = [];
  const testBlocks = [];

  for (let block = 1; block <= state.config.learning.blocks; block += 1) {
    let built = null;
    for (let attempt = 0; attempt < 100; attempt += 1) {
      const blockRng = createRng(seed + block * 1009 + attempt);
      try {
        built = buildLearningBlock(words, block, blockRng);
        break;
      } catch (_error) {
        built = null;
      }
    }
    if (!built) {
      throw new Error(`Could not generate learning block ${block}`);
    }
    learningBlocks.push({ block, trials: built });
    testBlocks.push({ block, trials: buildTestBlock(words, block, rng) });
  }

  return {
    schema: "cssl-validation-plan2-schedule-v1",
    participantId,
    seed,
    seedHex12: state.seedHex ? state.seedHex.slice(0, 12) : null,
    listId,
    responseMode: {
      learning: "click_or_keyboard",
      test: "click_5afc",
    },
    config: state.config,
    words,
    learningBlocks,
    testBlocks,
  };
}

function buildLearningBlock(words, block, rng) {
  const wordById = new Map(words.map((row) => [row.listWordId, row]));
  const remaining = new Map(words.map((row) => [row.listWordId, 3]));
  const pairCounts = new Map();
  const trials = [];

  for (let blockTrial = 1; blockTrial <= 20; blockTrial += 1) {
    const trialRows = [];

    for (let slot = 0; slot < 3; slot += 1) {
      const candidates = [];
      for (const [wordId, count] of remaining.entries()) {
        const row = wordById.get(wordId);
        if (count > 0 && !trialRows.includes(row)) {
          candidates.push(row);
        }
      }

      const valid = [];
      for (const candidate of candidates) {
        const proposed = trialRows.concat(candidate);
        if (!trialIsValid(proposed)) {
          continue;
        }
        const pairPenalty = trialRows.reduce((sum, item) => {
          return sum + (pairCounts.get(pairKey(candidate.listWordId, item.listWordId)) || 0);
        }, 0);
        valid.push({
          pairPenalty,
          remainingPenalty: -remaining.get(candidate.listWordId),
          randomTie: rng.random(),
          candidate,
        });
      }

      if (!valid.length) {
        throw new Error("Could not build a valid learning trial");
      }

      valid.sort((left, right) => {
        return (
          left.pairPenalty - right.pairPenalty
          || left.remainingPenalty - right.remainingPenalty
          || left.randomTie - right.randomTie
        );
      });

      const choice = valid[0].candidate;
      trialRows.push(choice);
      remaining.set(choice.listWordId, remaining.get(choice.listWordId) - 1);
    }

    const objectPositions = trialRows.slice();
    const wordOrder = trialRows.slice();
    rng.shuffle(objectPositions);
    rng.shuffle(wordOrder);

    for (const left of trialRows) {
      for (const right of trialRows) {
        if (left.listWordId < right.listWordId) {
          const key = pairKey(left.listWordId, right.listWordId);
          pairCounts.set(key, (pairCounts.get(key) || 0) + 1);
        }
      }
    }

    const objectPositionMap = {};
    objectPositions.forEach((row, index) => {
      objectPositionMap[String(index + 1)] = row.objectId;
    });

    trials.push({
      block,
      blockTrial,
      trialType: "learning",
      pairIds: trialRows.map((row) => row.listWordId),
      objectIds: objectPositions.map((row) => row.objectId),
      wordOrderPairIds: wordOrder.map((row) => row.listWordId),
      words: wordOrder.map((row) => row.word),
      objectPositions: objectPositionMap,
    });
  }

  for (const count of remaining.values()) {
    if (count !== 0) {
      throw new Error(`Unbalanced block ${block}`);
    }
  }

  return trials;
}

function buildTestBlock(words, block, rng) {
  const targets = words.slice();
  rng.shuffle(targets);
  const targetPositions = balancedTargetPositions(
    words.length,
    state.config.test.testOptions,
    rng,
  );
  return targets.map((target, index) => {
    const targetPosition = targetPositions[index];
    const foils = chooseFoils(target, words, rng);
    rng.shuffle(foils);
    const options = foils.slice();
    options.splice(targetPosition - 1, 0, target);
    return {
      block,
      blockTrial: index + 1,
      trialType: "test_5afc",
      targetPairId: target.listWordId,
      targetWord: target.word,
      targetObjectId: target.objectId,
      optionPairIds: options.map((row) => row.listWordId),
      optionObjectIds: options.map((row) => row.objectId),
      targetPosition,
      responseMethod: "click",
    };
  });
}

function balancedTargetPositions(trialCount, optionCount, rng) {
  if (trialCount % optionCount !== 0) {
    throw new Error(`Cannot balance ${trialCount} trials across ${optionCount} positions`);
  }
  const repeats = trialCount / optionCount;
  const positions = [];
  for (let position = 1; position <= optionCount; position += 1) {
    for (let repeat = 0; repeat < repeats; repeat += 1) {
      positions.push(position);
    }
  }
  rng.shuffle(positions);
  return positions;
}

function chooseFoils(target, words, rng) {
  const foils = [];
  const targetId = target.listWordId;

  const sameGroup = words.filter((row) => {
    return row.listWordId !== targetId
      && nonemptyGroup(row)
      && nonemptyGroup(row) === nonemptyGroup(target);
  });
  if (sameGroup.length) {
    foils.push(rng.choice(sameGroup));
  }

  const addFrom = (pool) => {
    const existingIds = new Set(foils.map((foil) => foil.listWordId));
    const usedFamilies = new Set([target, ...foils].map((row) => objectVisualFamily(row.objectId)));
    let available = pool.filter((row) => {
      return row.listWordId !== targetId
        && !existingIds.has(row.listWordId)
        && !usedFamilies.has(objectVisualFamily(row.objectId));
    });
    if (!available.length) {
      available = pool.filter((row) => {
        return row.listWordId !== targetId && !existingIds.has(row.listWordId);
      });
    }
    if (available.length && foils.length < 4) {
      foils.push(rng.choice(available));
    }
  };

  if (target.contrast === "control") {
    addFrom(words.filter((row) => row.contrast === "control"));
    addFrom(words.filter((row) => row.contrast === "control"));
    addFrom(words.filter((row) => row.contrast !== "control"));
    addFrom(words.filter((row) => row.contrast !== "control"));
  } else {
    addFrom(words.filter((row) => row.phonology === target.phonology));
    addFrom(words.filter((row) => row.contrast !== "control" && row.contrast !== target.contrast));
    addFrom(words.filter((row) => row.contrast === "control"));
  }

  while (foils.length < 4) {
    addFrom(words);
  }

  return foils.slice(0, 4);
}

function trialIsValid(candidates) {
  const ids = candidates.map((row) => row.listWordId);
  if (new Set(ids).size !== ids.length) {
    return false;
  }

  const groups = candidates.map(nonemptyGroup).filter(Boolean);
  if (new Set(groups).size !== groups.length) {
    return false;
  }

  const visualFamilies = candidates.map((row) => objectVisualFamily(row.objectId));
  return new Set(visualFamilies).size === visualFamilies.length;
}

function nonemptyGroup(row) {
  return String(row.contrastGroup || "");
}

function pairKey(left, right) {
  return left < right ? `${left}:${right}` : `${right}:${left}`;
}

function createRng(seed) {
  let value = seed >>> 0;
  return {
    random() {
      value = (value + 0x6D2B79F5) >>> 0;
      let t = value;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / UINT_32;
    },
    choice(items) {
      if (!items.length) {
        throw new Error("Cannot choose from an empty list");
      }
      return items[Math.floor(this.random() * items.length)];
    },
    shuffle(items) {
      for (let index = items.length - 1; index > 0; index -= 1) {
        const swapIndex = Math.floor(this.random() * (index + 1));
        [items[index], items[swapIndex]] = [items[swapIndex], items[index]];
      }
    },
  };
}

function getWord(pairId) {
  const word = state.wordByPairId.get(Number(pairId));
  if (!word) {
    throw new Error(`Unknown word ID: ${pairId}`);
  }
  return word;
}

function updateProgress(phase, title, completed, total) {
  els.phaseLabel.textContent = phase;
  els.taskTitle.textContent = title;
  els.progressText.textContent = `${completed} / ${total}`;
  const pct = total ? Math.max(0, Math.min(100, (completed / total) * 100)) : 0;
  els.progressBar.style.width = `${pct}%`;
}

function setSetupStatus(message, isError = false) {
  els.setupStatus.textContent = message;
  els.setupStatus.classList.toggle("error", isError);
}

function isSupportedChrome() {
  const userAgent = navigator.userAgent || "";
  const vendor = navigator.vendor || "";
  const brands = navigator.userAgentData && Array.isArray(navigator.userAgentData.brands)
    ? navigator.userAgentData.brands
    : [];
  const hasGoogleChromeBrand = brands.some((brand) => brand.brand === "Google Chrome");
  const hasChromeUa = /Chrome\//.test(userAgent) && /Google Inc/.test(vendor);
  const blockedChromiumFamily = /Edg\/|OPR\/|Opera|Firefox\/|CriOS|FxiOS/.test(userAgent);
  return (hasGoogleChromeBrand || hasChromeUa) && !blockedChromiumFamily;
}

function showUnsupportedBrowser() {
  const setupTitle = document.getElementById("setupTitle");
  if (setupTitle) {
    setupTitle.textContent = "Chromeで開いてください";
  }
  els.startButton.disabled = true;
  setSetupStatus("この課題はGoogle Chromeのみ対応です。Google Chromeで開き直してください。", true);
}

function buildExportPayload() {
  return {
    schema: "cssl-validation-plan2-browser-export-v1",
    participantId: state.participantId,
    seed: state.seed,
    seedHex: state.seedHex,
    listId: state.listId,
    listOverride: state.listOverride,
    sessionStartedAt: state.sessionStartedAt,
    sessionCompletedAt: state.sessionCompletedAt,
    userAgent: navigator.userAgent,
    Config: state.config,
    PairMap: state.words,
    Schedule: state.schedule,
    Practice: state.practiceEvents,
    LearningTrials: state.learningTrials,
    LearningEvents: state.learningEvents,
    Data: state.testData,
    ModelReady: buildModelReadyRows(),
    Summary: buildSummary(),
  };
}

function downloadWorkbookXlsx() {
  const sheets = buildWorkbookSheets();
  const blob = buildXlsxBlob(sheets);
  downloadBlob(blob, exportFilename("xlsx"));
}

function buildWorkbookSheets() {
  const metadata = [{
    schema: "cssl-validation-plan2-xlsx-v1",
    participantId: state.participantId,
    seed: state.seed,
    seedHex12: state.seedHex.slice(0, 12),
    listId: state.listId,
    listOverride: state.listOverride || "",
    sessionStartedAt: state.sessionStartedAt,
    sessionCompletedAt: state.sessionCompletedAt,
    userAgent: navigator.userAgent,
  }];

  const pairMap = state.words.map((row) => ({
    ...row,
    objectImage: objectImagePath(row.objectId),
    objectVisualFamily: objectVisualFamily(row.objectId),
  }));

  return [
    { name: "Metadata", rows: metadata },
    { name: "Summary", rows: summaryRows() },
    { name: "Data", rows: state.testData.map(flattenExportRow) },
    { name: "ModelReady", rows: buildModelReadyRows() },
    { name: "LearningEvents", rows: state.learningEvents.map(flattenExportRow) },
    { name: "LearningTrials", rows: state.learningTrials.map(flattenExportRow) },
    { name: "Practice", rows: state.practiceEvents.map(flattenExportRow) },
    { name: "PairMap", rows: pairMap.map(flattenExportRow) },
    { name: "LearningSchedule", rows: flattenScheduleTrials(state.schedule.learningBlocks, "learning") },
    { name: "TestSchedule", rows: flattenScheduleTrials(state.schedule.testBlocks, "test_5afc") },
    { name: "Config", rows: keyValueRows(state.config) },
    { name: "Notes", rows: notesRows() },
  ];
}

function buildModelReadyRows() {
  const rows = [];
  const learningByBlock = groupRowsByNumber(state.learningEvents, "block");
  const testByBlock = groupRowsByNumber(state.testData, "block");
  const latestLearningByPairEncounter = new Map();

  for (const event of state.learningEvents) {
    latestLearningByPairEncounter.set(`${event.pairId}:${event.encounterIndex}`, event);
  }

  let observationSeq = 0;
  const blockCount = state.config && state.config.learning
    ? Number(state.config.learning.blocks)
    : 0;

  for (let block = 1; block <= blockCount; block += 1) {
    const learningRows = (learningByBlock.get(block) || [])
      .slice()
      .sort((left, right) => left.eventSeq - right.eventSeq);
    for (const event of learningRows) {
      observationSeq += 1;
      rows.push(modelReadyLearningRow(event, observationSeq));
    }

    const testRows = (testByBlock.get(block) || [])
      .slice()
      .sort((left, right) => left.blockTrial - right.blockTrial);
    for (const trial of testRows) {
      observationSeq += 1;
      const previous = latestLearningByPairEncounter.get(
        `${trial.targetPairId}:${trial.encountersCompletedForWord}`,
      ) || null;
      rows.push(modelReadyTestRow(trial, previous, observationSeq));
    }
  }

  return rows;
}

function modelReadyLearningRow(event, observationSeq) {
  const sameAsPrevious = sameResponseFlag(event.responseObjectId, event.previousResponseObjectId);
  const previousResponseInChoiceSet = choiceSetContainsFlag(
    event.contextObjectIds,
    event.previousResponseObjectId,
  );
  return {
    participantId: event.participantId,
    seed: event.seed,
    seedHex12: event.seedHex12,
    listId: event.listId,
    observationSeq,
    observationType: "learning_3afc",
    block: event.block,
    blockTrial: event.blockTrial,
    wordEventInTrial: event.wordEventInTrial,
    pairId: event.pairId,
    word: event.word,
    ttsText: event.ttsText,
    targetObjectId: event.targetObjectId,
    contrast: event.contrast,
    contrastGroup: event.contrastGroup,
    phonology: event.phonology,
    syllableCount: event.syllableCount,
    syllableTemplate: event.syllableTemplate,
    phones: event.phones,
    ipaTarget: event.ipaTarget,
    phonologicalNeighborhoodSize: event.phonologicalNeighborhoodSize,
    nearestRealWordDistance: event.nearestRealWordDistance,
    nearestRealWords: event.nearestRealWords,
    encounterIndex: event.encounterIndex,
    encountersCompletedForWord: event.encounterIndex,
    choiceSetSize: 3,
    chanceLevel: roundNumber(1 / 3, 6),
    optionObjectIds: jsonCell(event.contextObjectIds),
    optionPairIds: jsonCell(event.contextPairIds),
    targetPosition: event.targetPosition,
    responseObjectId: event.responseObjectId,
    responsePosition: event.responsePosition,
    responseSource: event.responseSource,
    correct: boolFlag(event.correct),
    noResponse: 0,
    timedOut: 0,
    rtMs: event.rtMs,
    responseTimeoutMs: "",
    previousResponseObjectId: blankNull(event.previousResponseObjectId),
    previousCorrect: boolFlag(event.previousCorrect),
    previousIncorrect: inverseBoolFlag(event.previousCorrect),
    previousRtMs: blankNull(event.previousRtMs),
    hasPreviousForWord: event.previousCorrect === null ? 0 : 1,
    previousResponseInChoiceSet,
    sameResponseAsPrevious: sameAsPrevious,
    switchedFromPreviousResponse: inverseFlag(sameAsPrevious),
    maintainedAvailablePreviousResponse: conditionalFlag(
      previousResponseInChoiceSet === 1,
      sameAsPrevious,
    ),
    switchedAwayFromAvailablePreviousResponse: conditionalFlag(
      previousResponseInChoiceSet === 1,
      inverseFlag(sameAsPrevious),
    ),
    forcedSwitchFromUnavailablePreviousResponse: conditionalFlag(
      previousResponseInChoiceSet === 0,
      inverseFlag(sameAsPrevious),
    ),
    stayedAfterPreviousCorrect: conditionalFlag(event.previousCorrect === true, sameAsPrevious),
    switchedAfterPreviousIncorrect: conditionalFlag(event.previousCorrect === false, inverseFlag(sameAsPrevious)),
    audioSource: event.audioSource,
    audioPlayOk: boolFlag(event.audioPlayOk),
    audioStartedAtMs: event.audioStartedAtMs,
    audioEndedAtMs: event.audioEndedAtMs,
    replayAllowed: "",
    replayCount: "",
  };
}

function modelReadyTestRow(trial, previous, observationSeq) {
  const previousResponseObjectId = previous ? previous.responseObjectId : null;
  const previousCorrect = previous ? previous.correct : null;
  const sameAsPrevious = sameResponseFlag(trial.responseObjectId, previousResponseObjectId);
  const previousResponseInChoiceSet = choiceSetContainsFlag(
    trial.optionObjectIds,
    previousResponseObjectId,
  );
  return {
    participantId: trial.participantId,
    seed: trial.seed,
    seedHex12: trial.seedHex12,
    listId: trial.listId,
    observationSeq,
    observationType: "test_5afc",
    block: trial.block,
    blockTrial: trial.blockTrial,
    wordEventInTrial: "",
    pairId: trial.targetPairId,
    word: trial.targetWord,
    ttsText: trial.ttsText,
    targetObjectId: trial.targetObjectId,
    contrast: trial.contrast,
    contrastGroup: trial.contrastGroup,
    phonology: trial.phonology,
    syllableCount: trial.syllableCount,
    syllableTemplate: trial.syllableTemplate,
    phones: trial.phones,
    ipaTarget: trial.ipaTarget,
    phonologicalNeighborhoodSize: trial.phonologicalNeighborhoodSize,
    nearestRealWordDistance: trial.nearestRealWordDistance,
    nearestRealWords: trial.nearestRealWords,
    encounterIndex: "",
    encountersCompletedForWord: trial.encountersCompletedForWord,
    choiceSetSize: 5,
    chanceLevel: 0.2,
    optionObjectIds: jsonCell(trial.optionObjectIds),
    optionPairIds: jsonCell(trial.optionPairIds),
    targetPosition: trial.targetPosition,
    responseObjectId: blankNull(trial.responseObjectId),
    responsePosition: blankNull(trial.responsePosition),
    responseSource: trial.responseSource,
    correct: boolFlag(trial.correct),
    noResponse: boolFlag(trial.noResponse),
    timedOut: boolFlag(trial.responseTimedOut),
    rtMs: trial.rtMs,
    responseTimeoutMs: trial.responseTimeoutMs,
    previousResponseObjectId: blankNull(previousResponseObjectId),
    previousCorrect: boolFlag(previousCorrect),
    previousIncorrect: inverseBoolFlag(previousCorrect),
    previousRtMs: previous ? previous.rtMs : "",
    hasPreviousForWord: previous ? 1 : 0,
    previousResponseInChoiceSet,
    sameResponseAsPrevious: sameAsPrevious,
    switchedFromPreviousResponse: inverseFlag(sameAsPrevious),
    maintainedAvailablePreviousResponse: conditionalFlag(
      previousResponseInChoiceSet === 1,
      sameAsPrevious,
    ),
    switchedAwayFromAvailablePreviousResponse: conditionalFlag(
      previousResponseInChoiceSet === 1,
      inverseFlag(sameAsPrevious),
    ),
    forcedSwitchFromUnavailablePreviousResponse: conditionalFlag(
      previousResponseInChoiceSet === 0,
      inverseFlag(sameAsPrevious),
    ),
    stayedAfterPreviousCorrect: conditionalFlag(previousCorrect === true, sameAsPrevious),
    switchedAfterPreviousIncorrect: conditionalFlag(previousCorrect === false, inverseFlag(sameAsPrevious)),
    audioSource: trial.audioSource,
    audioPlayOk: boolFlag(trial.audioPlayOk),
    audioStartedAtMs: trial.audioStartedAtMs,
    audioEndedAtMs: trial.audioEndedAtMs,
    replayAllowed: boolFlag(trial.replayAllowed),
    replayCount: trial.replayCount,
  };
}

function groupRowsByNumber(rows, key) {
  const groups = new Map();
  for (const row of rows) {
    const groupKey = Number(row[key]);
    if (!groups.has(groupKey)) {
      groups.set(groupKey, []);
    }
    groups.get(groupKey).push(row);
  }
  return groups;
}

function sameResponseFlag(currentResponseObjectId, previousResponseObjectId) {
  if (currentResponseObjectId === null
      || typeof currentResponseObjectId === "undefined"
      || previousResponseObjectId === null
      || typeof previousResponseObjectId === "undefined") {
    return "";
  }
  return Number(currentResponseObjectId) === Number(previousResponseObjectId) ? 1 : 0;
}

function choiceSetContainsFlag(optionObjectIds, objectId) {
  if (objectId === null || typeof objectId === "undefined" || objectId === "") {
    return "";
  }
  if (!Array.isArray(optionObjectIds)) {
    return "";
  }
  const target = Number(objectId);
  return optionObjectIds.map(Number).includes(target) ? 1 : 0;
}

function boolFlag(value) {
  if (value === null || typeof value === "undefined" || value === "") {
    return "";
  }
  return value ? 1 : 0;
}

function inverseBoolFlag(value) {
  if (value === null || typeof value === "undefined" || value === "") {
    return "";
  }
  return value ? 0 : 1;
}

function inverseFlag(value) {
  if (value === null || typeof value === "undefined" || value === "") {
    return "";
  }
  return value ? 0 : 1;
}

function conditionalFlag(condition, value) {
  return condition ? value : "";
}

function blankNull(value) {
  return value === null || typeof value === "undefined" ? "" : value;
}

function jsonCell(value) {
  return Array.isArray(value) || (value && typeof value === "object")
    ? JSON.stringify(value)
    : blankNull(value);
}

function roundNumber(value, digits) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function summaryRows() {
  const summary = buildSummary();
  const rows = [{
    metric: "learningEventCount",
    value: summary.learningEventCount,
    scope: "all learning word events",
  }, {
    metric: "learningTrialCount",
    value: summary.learningTrialCount,
    scope: "all learning trials",
  }, {
    metric: "testTrialCount",
    value: summary.testTrialCount,
    scope: "all 5AFC trials",
  }, {
    metric: "testNoResponseCount",
    value: summary.testNoResponseCount,
    scope: "all 5AFC trials",
  }, {
    metric: "testTimeoutCount",
    value: summary.testTimeoutCount,
    scope: "all 5AFC trials",
  }];

  for (const [block, data] of Object.entries(summary.testByBlock)) {
    rows.push({
      metric: "testAccuracy",
      block,
      value: data.accuracy,
      correct: data.correct,
      total: data.total,
      noResponse: data.noResponse,
      timeout: data.timeout,
      scope: "5AFC by block",
    });
  }
  return rows;
}

function flattenScheduleTrials(blocks, phase) {
  const rows = [];
  for (const block of blocks) {
    for (const trial of block.trials) {
      rows.push(flattenExportRow({ phase, ...trial }));
    }
  }
  return rows;
}

function keyValueRows(value, prefix = "") {
  const rows = [];
  if (value && typeof value === "object" && !Array.isArray(value)) {
    for (const [key, item] of Object.entries(value)) {
      rows.push(...keyValueRows(item, prefix ? `${prefix}.${key}` : key));
    }
  } else {
    rows.push({ key: prefix, value: formatExportValue(value) });
  }
  return rows;
}

function notesRows() {
  return [
    { sheet: "General", note: "The task is intended for Google Chrome only; other browsers are blocked at startup." },
    { sheet: "Practice", note: "The first practice entry is the volume check. Exclude all practice rows from model fitting." },
    { sheet: "Data", note: "5AFC test trials. Primary block-level outcome and Berens-style first-correct summaries can be computed from this sheet." },
    { sheet: "Data", note: `5AFC response timeout is ${TEST_RESPONSE_TIMEOUT_MS} ms. Timeout rows are saved with noResponse=true, responseSource=timeout, and correct=false.` },
    { sheet: "Data", note: "Main-task 5AFC replay is disabled so phonological perception and response timing remain standardized after the initial volume check." },
    { sheet: "ModelReady", note: "Chronological learning and 5AFC observations with numeric flags for switching and HMM-style analyses." },
    { sheet: "ModelReady", note: "previousResponseInChoiceSet and related available/unavailable switch flags support no-feedback PbV analyses using learner-available evidence." },
    { sheet: "LearningEvents", note: "One row per spoken word during learning. This is the primary sheet for encounter-index switching analyses." },
    { sheet: "LearningTrials", note: "One row per 3-word/3-object learning context." },
    { sheet: "PairMap", note: "Participant-specific word-object mapping, phonological condition, and visual family." },
    { sheet: "LearningSchedule", note: "Deterministic schedule generated from participant ID. Same seed reproduces this schedule." },
    { sheet: "TestSchedule", note: "Deterministic 5AFC target and option order. Target position is balanced within each block." },
  ];
}

function buildSummary() {
  const byBlock = {};
  for (const row of state.testData) {
    if (!byBlock[row.block]) {
      byBlock[row.block] = { correct: 0, total: 0, noResponse: 0, timeout: 0, accuracy: 0 };
    }
    byBlock[row.block].total += 1;
    byBlock[row.block].correct += row.correct ? 1 : 0;
    byBlock[row.block].noResponse += row.noResponse ? 1 : 0;
    byBlock[row.block].timeout += row.responseTimedOut ? 1 : 0;
  }
  for (const block of Object.keys(byBlock)) {
    byBlock[block].accuracy = byBlock[block].total
      ? byBlock[block].correct / byBlock[block].total
      : null;
  }
  return {
    learningEventCount: state.learningEvents.length,
    learningTrialCount: state.learningTrials.length,
    testTrialCount: state.testData.length,
    testNoResponseCount: state.testData.filter((row) => row.noResponse).length,
    testTimeoutCount: state.testData.filter((row) => row.responseTimedOut).length,
    testByBlock: byBlock,
  };
}

function flattenExportRow(row) {
  const flattened = {};
  for (const [key, value] of Object.entries(row)) {
    flattened[key] = formatExportValue(value);
  }
  return flattened;
}

function formatExportValue(value) {
  if (value === null || typeof value === "undefined") {
    return "";
  }
  if (Array.isArray(value) || typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function buildXlsxBlob(sheets) {
  const safeSheets = sheets.map((sheet, index) => ({
    name: sanitizeSheetName(sheet.name || `Sheet${index + 1}`),
    rows: Array.isArray(sheet.rows) ? sheet.rows : [],
  }));
  const entries = {};
  entries["[Content_Types].xml"] = contentTypesXml(safeSheets.length);
  entries["_rels/.rels"] = rootRelsXml();
  entries["xl/workbook.xml"] = workbookXml(safeSheets);
  entries["xl/_rels/workbook.xml.rels"] = workbookRelsXml(safeSheets.length);
  entries["xl/styles.xml"] = stylesXml();
  safeSheets.forEach((sheet, index) => {
    entries[`xl/worksheets/sheet${index + 1}.xml`] = worksheetXml(sheet.rows);
  });
  return new Blob([zipStore(entries)], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
}

function sanitizeSheetName(name) {
  return String(name).replace(/[\[\]:*?/\\]/g, "_").slice(0, 31) || "Sheet";
}

function contentTypesXml(sheetCount) {
  const sheetOverrides = Array.from({ length: sheetCount }, (_item, index) => {
    return `<Override PartName="/xl/worksheets/sheet${index + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`;
  }).join("");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  ${sheetOverrides}
</Types>`;
}

function rootRelsXml() {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`;
}

function workbookXml(sheets) {
  const sheetXml = sheets.map((sheet, index) => {
    return `<sheet name="${xmlEscape(sheet.name)}" sheetId="${index + 1}" r:id="rId${index + 1}"/>`;
  }).join("");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>${sheetXml}</sheets>
</workbook>`;
}

function workbookRelsXml(sheetCount) {
  const sheetRels = Array.from({ length: sheetCount }, (_item, index) => {
    return `<Relationship Id="rId${index + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${index + 1}.xml"/>`;
  }).join("");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  ${sheetRels}
  <Relationship Id="rId${sheetCount + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>`;
}

function stylesXml() {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border/></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
  <dxfs count="0"/>
  <tableStyles count="0" defaultTableStyle="TableStyleMedium2" defaultPivotStyle="PivotStyleLight16"/>
</styleSheet>`;
}

function worksheetXml(rows) {
  const headers = collectHeaders(rows);
  const sheetRows = [headers, ...rows.map((row) => headers.map((header) => row[header]))];
  const rowXml = sheetRows.map((row, rowIndex) => {
    const cells = row.map((value, colIndex) => cellXml(value, colIndex, rowIndex)).join("");
    return `<row r="${rowIndex + 1}">${cells}</row>`;
  }).join("");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>${rowXml}</sheetData>
</worksheet>`;
}

function collectHeaders(rows) {
  const headers = [];
  for (const row of rows) {
    for (const key of Object.keys(row)) {
      if (!headers.includes(key)) {
        headers.push(key);
      }
    }
  }
  return headers.length ? headers : ["empty"];
}

function cellXml(value, colIndex, rowIndex) {
  const ref = `${columnName(colIndex)}${rowIndex + 1}`;
  if (typeof value === "number" && Number.isFinite(value)) {
    return `<c r="${ref}"><v>${value}</v></c>`;
  }
  const text = value === null || typeof value === "undefined" ? "" : String(value);
  return `<c r="${ref}" t="inlineStr"><is><t>${xmlEscape(text)}</t></is></c>`;
}

function columnName(index) {
  let name = "";
  let value = index + 1;
  while (value > 0) {
    const remainder = (value - 1) % 26;
    name = String.fromCharCode(65 + remainder) + name;
    value = Math.floor((value - 1) / 26);
  }
  return name;
}

function xmlEscape(value) {
  return String(value)
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function zipStore(entries) {
  const encoder = new TextEncoder();
  const localParts = [];
  const centralParts = [];
  let offset = 0;

  for (const [filename, content] of Object.entries(entries)) {
    const nameBytes = encoder.encode(filename);
    const dataBytes = encoder.encode(content);
    const crc = crc32(dataBytes);
    const localHeader = zipLocalHeader(nameBytes, dataBytes, crc);
    localParts.push(localHeader, dataBytes);
    centralParts.push(zipCentralHeader(nameBytes, dataBytes, crc, offset));
    offset += localHeader.length + dataBytes.length;
  }

  const centralSize = centralParts.reduce((sum, part) => sum + part.length, 0);
  const centralOffset = offset;
  const endRecord = zipEndRecord(Object.keys(entries).length, centralSize, centralOffset);
  return concatUint8Arrays([...localParts, ...centralParts, endRecord]);
}

function zipLocalHeader(nameBytes, dataBytes, crc) {
  const header = new Uint8Array(30 + nameBytes.length);
  const view = new DataView(header.buffer);
  view.setUint32(0, 0x04034b50, true);
  view.setUint16(4, 20, true);
  view.setUint16(6, 0, true);
  view.setUint16(8, 0, true);
  view.setUint16(10, 0, true);
  view.setUint16(12, 0, true);
  view.setUint32(14, crc, true);
  view.setUint32(18, dataBytes.length, true);
  view.setUint32(22, dataBytes.length, true);
  view.setUint16(26, nameBytes.length, true);
  view.setUint16(28, 0, true);
  header.set(nameBytes, 30);
  return header;
}

function zipCentralHeader(nameBytes, dataBytes, crc, offset) {
  const header = new Uint8Array(46 + nameBytes.length);
  const view = new DataView(header.buffer);
  view.setUint32(0, 0x02014b50, true);
  view.setUint16(4, 20, true);
  view.setUint16(6, 20, true);
  view.setUint16(8, 0, true);
  view.setUint16(10, 0, true);
  view.setUint16(12, 0, true);
  view.setUint16(14, 0, true);
  view.setUint32(16, crc, true);
  view.setUint32(20, dataBytes.length, true);
  view.setUint32(24, dataBytes.length, true);
  view.setUint16(28, nameBytes.length, true);
  view.setUint16(30, 0, true);
  view.setUint16(32, 0, true);
  view.setUint16(34, 0, true);
  view.setUint16(36, 0, true);
  view.setUint32(38, 0, true);
  view.setUint32(42, offset, true);
  header.set(nameBytes, 46);
  return header;
}

function zipEndRecord(entryCount, centralSize, centralOffset) {
  const header = new Uint8Array(22);
  const view = new DataView(header.buffer);
  view.setUint32(0, 0x06054b50, true);
  view.setUint16(4, 0, true);
  view.setUint16(6, 0, true);
  view.setUint16(8, entryCount, true);
  view.setUint16(10, entryCount, true);
  view.setUint32(12, centralSize, true);
  view.setUint32(16, centralOffset, true);
  view.setUint16(20, 0, true);
  return header;
}

function concatUint8Arrays(parts) {
  const total = parts.reduce((sum, part) => sum + part.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

function crc32(bytes) {
  let crc = 0xFFFFFFFF;
  for (const byte of bytes) {
    crc = CRC32_TABLE[(crc ^ byte) & 0xFF] ^ (crc >>> 8);
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

const CRC32_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i += 1) {
    let value = i;
    for (let bit = 0; bit < 8; bit += 1) {
      value = value & 1 ? 0xEDB88320 ^ (value >>> 1) : value >>> 1;
    }
    table[i] = value >>> 0;
  }
  return table;
})();

function exportFilename(suffix) {
  return `sub-${safeFilename(state.participantId)}_plan2_${suffix}`;
}

function safeFilename(text) {
  return text.replace(/[^a-zA-Z0-9_-]/g, "_") || "participant";
}

function objectImagePath(objectId) {
  const id = Number(objectId);
  if (id >= 900) {
    return `images/objects/practice_${id}.svg`;
  }
  return `images/objects/object_${String(id).padStart(3, "0")}.svg`;
}

function svgFallbackForObject(objectId) {
  const wrapper = document.createElement("span");
  wrapper.innerHTML = renderObjectSvg(objectId).trim();
  return wrapper.firstElementChild;
}

function objectVisualFamily(objectId) {
  const id = Number(objectId);
  const variant = Math.floor((id - 1) / 8);
  return ((id - 1) + variant * 3) % 8;
}

function renderObjectSvg(objectId) {
  const id = Number(objectId);
  const palettes = [
    ["#0f766e", "#f59e0b", "#e6fffb"],
    ["#2563eb", "#ef6c35", "#eef5ff"],
    ["#7c3aed", "#16a34a", "#f4edff"],
    ["#be123c", "#0891b2", "#fff1f3"],
    ["#6b4f2a", "#2f855a", "#fff7e6"],
    ["#0f4c81", "#d97706", "#edf7ff"],
    ["#8a3ffc", "#d9480f", "#f7f0ff"],
    ["#006d77", "#9b2226", "#e9fbf8"],
  ];
  const variant = Math.floor((id - 1) / 8);
  const palette = palettes[((id - 1) * 3 + variant) % palettes.length];
  const shape = ((id - 1) + variant * 3) % 8;
  const rotate = ((id * 17) % 34) - 17;
  const [main, accent, pale] = palette;
  const dotShift = (variant % 4) * 8;
  const strokeWidth = 7 + (variant % 3);
  const rotateAttr = `rotate(${rotate} 100 100)`;

  const shadow = '<ellipse cx="100" cy="178" rx="55" ry="11" fill="#17201d" opacity="0.12"/>';
  const decorations = `
    <circle cx="${66 + dotShift}" cy="70" r="${9 + (variant % 2) * 3}" fill="${accent}" opacity="0.92"/>
    <circle cx="${132 - dotShift / 2}" cy="124" r="${7 + (variant % 3)}" fill="${accent}" opacity="0.78"/>
    <path d="M64 148 C86 ${132 - dotShift}, 114 ${166 - dotShift}, 138 142" fill="none" stroke="${accent}" stroke-width="7" stroke-linecap="round" opacity="0.82"/>
  `;

  let body = "";
  if (shape === 0) {
    body = `<path d="M100 28 L156 61 L146 134 L100 171 L54 134 L44 61 Z" fill="${pale}" stroke="${main}" stroke-width="${strokeWidth}" stroke-linejoin="round"/>`;
  } else if (shape === 1) {
    body = `<rect x="45" y="43" width="110" height="110" rx="${24 + variant * 2}" fill="${pale}" stroke="${main}" stroke-width="${strokeWidth}"/>`;
  } else if (shape === 2) {
    body = `<path d="M100 32 C136 32 162 58 162 93 C162 134 130 164 90 164 C58 164 38 143 38 111 C38 66 60 32 100 32 Z" fill="${pale}" stroke="${main}" stroke-width="${strokeWidth}" stroke-linejoin="round"/>`;
  } else if (shape === 3) {
    body = `<path d="M56 54 C88 26 132 30 152 62 C174 98 146 154 102 166 C61 177 30 143 42 98 C47 80 44 66 56 54 Z" fill="${pale}" stroke="${main}" stroke-width="${strokeWidth}" stroke-linejoin="round"/>`;
  } else if (shape === 4) {
    body = `<path d="M100 26 L118 72 L166 76 L128 106 L141 154 L100 128 L59 154 L72 106 L34 76 L82 72 Z" fill="${pale}" stroke="${main}" stroke-width="${strokeWidth}" stroke-linejoin="round"/>`;
  } else if (shape === 5) {
    body = `<path d="M48 83 C48 55 69 38 100 38 C131 38 152 55 152 83 L152 127 C152 148 131 164 100 164 C69 164 48 148 48 127 Z" fill="${pale}" stroke="${main}" stroke-width="${strokeWidth}"/>`;
  } else if (shape === 6) {
    body = `<path d="M100 31 L159 96 L126 164 L74 164 L41 96 Z" fill="${pale}" stroke="${main}" stroke-width="${strokeWidth}" stroke-linejoin="round"/>`;
  } else {
    body = `<path d="M42 101 C42 62 62 42 101 42 C140 42 158 62 158 101 C158 140 140 158 101 158 C62 158 42 140 42 101 Z M74 101 C74 119 84 128 101 128 C118 128 126 119 126 101 C126 84 118 74 101 74 C84 74 74 84 74 101 Z" fill="${pale}" stroke="${main}" stroke-width="${strokeWidth}" fill-rule="evenodd"/>`;
  }

  return `
    <svg viewBox="0 0 200 200" role="img" focusable="false">
      ${shadow}
      <g transform="${rotateAttr}">
        ${body}
        ${decorations}
      </g>
    </svg>
  `;
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function roundMs(value) {
  return Math.round(value * 1000) / 1000;
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
