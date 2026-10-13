const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const list = document.querySelector('#admin-list');
const status = document.querySelector('#admin-status');

function notify(message, isError = false) {
  status.textContent = message;
  status.hidden = false;
  status.classList.toggle('error', isError);
}

async function loadAdminList() {
  const response = await fetch('/api/admin/kudos');
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Could not load messages.');
  list.replaceChildren();
  if (!data.items.length) {
    const empty = document.createElement('p');
    empty.className = 'muted';
    empty.textContent = 'There are no messages to review yet.';
    list.append(empty);
    return;
  }
  data.items.forEach((item) => {
    const card = document.createElement('article');
    card.className = 'admin-card';
    const head = document.createElement('div');
    head.className = 'admin-card-head';
    const names = document.createElement('strong');
    names.textContent = `${item.sender_name} → ${item.recipient_name}`;
    const tag = document.createElement('span');
    tag.className = `status-tag${item.is_visible ? '' : ' hidden'}`;
    tag.textContent = item.is_deleted ? 'Removed' : item.is_visible ? 'Visible' : 'Hidden';
    head.append(names, tag);
    const text = document.createElement('p');
    text.textContent = item.message;
    const when = document.createElement('p');
    when.className = 'small muted';
    when.textContent = new Date(item.created_at).toLocaleString();
    card.append(head, text, when);
    if (item.moderation_reason) {
      const reason = document.createElement('p');
      reason.className = 'small muted';
      reason.textContent = `Latest moderation reason: ${item.moderation_reason}`;
      card.append(reason);
    }
    const actions = document.createElement('div');
    actions.className = 'admin-actions';
    if (!item.is_visible && !item.is_deleted) {
      actions.append(makeAction(item.id, 'restore', 'Show again', 'secondary'));
    } else if (item.is_visible) {
      actions.append(makeAction(item.id, 'hide', 'Hide', 'secondary'));
    }
    if (!item.is_deleted) actions.append(makeAction(item.id, 'delete', 'Remove', 'danger'));
    card.append(actions);
    const historyButton = document.createElement('button');
    historyButton.type = 'button';
    historyButton.className = 'button quiet';
    historyButton.textContent = 'View action history';
    historyButton.addEventListener('click', () => showHistory(item.id, card));
    card.append(historyButton);
    list.append(card);
  });
}

function makeAction(id, action, label, style) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = `button ${style}`;
  button.textContent = label;
  button.addEventListener('click', async () => {
    const reason = window.prompt(`Why are you choosing to ${action} this message?`);
    if (reason === null) return;
    try {
      const response = await fetch(`/api/admin/kudos/${id}/moderate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify({ action, reason }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Action could not be saved.');
      notify(data.message);
      await loadAdminList();
    } catch (error) {
      notify(error.message, true);
    }
  });
  return button;
}

async function showHistory(id, card) {
  try {
    const response = await fetch(`/api/admin/kudos/${id}/history`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not load history.');
    const box = document.createElement('div');
    box.className = 'history';
    box.textContent = data.events.length
      ? data.events.map((event) => `${event.action} by ${event.admin_name}: ${event.reason} (${new Date(event.created_at).toLocaleString()})`).join('\n')
      : 'No moderation actions have been recorded.';
    const old = card.querySelector('.history');
    if (old) old.remove();
    card.append(box);
  } catch (error) {
    notify(error.message, true);
  }
}

loadAdminList().catch((error) => notify(error.message, true));
