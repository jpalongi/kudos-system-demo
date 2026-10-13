const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const form = document.querySelector('#kudos-form');
const message = document.querySelector('#message');
const count = document.querySelector('#message-count');
const statusBox = document.querySelector('#form-status');
const feed = document.querySelector('#feed');
const loadMore = document.querySelector('#load-more');
let nextOffset = 0;

function showStatus(text, isError = false) {
  statusBox.textContent = text;
  statusBox.hidden = false;
  statusBox.classList.toggle('error', isError);
}

function addCard(item) {
  const card = document.createElement('article');
  card.className = 'kudos-card';
  const avatar = document.createElement('span');
  avatar.className = 'avatar';
  avatar.textContent = item.sender_name.trim().charAt(0).toUpperCase();
  avatar.setAttribute('aria-hidden', 'true');
  const content = document.createElement('div');
  const meta = document.createElement('div');
  meta.className = 'kudos-meta';
  const sender = document.createElement('strong');
  sender.textContent = item.sender_name;
  const recipient = document.createElement('strong');
  recipient.textContent = item.recipient_name;
  meta.append(sender, document.createTextNode(' gave kudos to '), recipient);
  const time = document.createElement('div');
  time.className = 'kudos-time';
  time.textContent = new Date(item.created_at).toLocaleString();
  const text = document.createElement('p');
  text.className = 'kudos-message';
  text.textContent = item.message;
  content.append(meta, time, text);
  card.append(avatar, content);
  feed.append(card);
}

async function loadFeed(reset = false) {
  if (reset) {
    feed.replaceChildren();
    nextOffset = 0;
  }
  try {
    const response = await fetch(`/api/kudos?offset=${nextOffset}&limit=20`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not load the feed.');
    if (reset && data.items.length === 0) {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = 'No kudos here yet. You could be the first to send one!';
      feed.append(empty);
    } else {
      data.items.forEach(addCard);
    }
    nextOffset = data.next_offset ?? nextOffset;
    loadMore.hidden = data.next_offset === null;
  } catch (error) {
    const message = document.createElement('p');
    message.className = 'notice error';
    message.textContent = error.message;
    feed.append(message);
  }
}

message.addEventListener('input', () => {
  count.textContent = `${message.value.length} / 500`;
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = document.querySelector('#submit-kudos');
  button.disabled = true;
  statusBox.hidden = true;
  try {
    const response = await fetch('/api/kudos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
      body: JSON.stringify({
        recipient_id: document.querySelector('#recipient_id').value,
        message: message.value,
        idempotency_key: crypto.randomUUID(),
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Kudos could not be sent.');
    form.reset();
    count.textContent = '0 / 500';
    showStatus('Your kudos has been sent. Thanks for spreading a little appreciation!');
    await loadFeed(true);
  } catch (error) {
    showStatus(error.message, true);
  } finally {
    button.disabled = false;
  }
});

loadMore.addEventListener('click', () => loadFeed(false));
loadFeed(true);
