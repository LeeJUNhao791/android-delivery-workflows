const recoveryBudgetMs = 20000;
const originalSessionGraceMs = 5000;

export async function recoverWifi(state, ipRestoredAt, waitForFrame, replaceSession) {
  const remaining = () => ipRestoredAt + recoveryBudgetMs - performance.now();
  state.reconnectAttempts = 0;
  state.reconnect = 'original peer connection';
  let frame = await waitForFrame(replaceSession ? Math.min(originalSessionGraceMs, remaining()) : remaining());
  if (!frame && replaceSession && remaining() > 0) {
    state.reconnectAttempts = 1;
    state.reconnect = 'new peer connection';
    await replaceSession();
    if (remaining() > 0) frame = await waitForFrame(remaining());
  }
  if (!frame || remaining() < 0) throw new Error('No video frame after Wi-Fi returned');
  state.nextFrameAfterIpMs = Math.round(performance.now() - ipRestoredAt);
  state.iceAfterRecovery = frame.iceState;
}
