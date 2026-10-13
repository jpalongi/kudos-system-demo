# Kudos Feature Specification

## What the feature is for

This feature will let employees thank and recognise their colleagues on the company portal. Employees can choose someone, write a short message and post it. Other signed-in employees can see recent messages in a feed.

An administrator should be able to hide or remove messages that are inappropriate. In this specification, “public feed” means visible to signed-in employees on the portal, not visible to everyone on the internet.

## What people should be able to do

### User stories

1. As an employee, I want to choose a colleague so I can send them kudos.
2. As an employee, I want to write a message of appreciation and submit it.
3. As an employee, I want to see recent kudos in a feed on the dashboard.
4. As an administrator, I want to hide or remove an inappropriate message.
5. As an administrator, I want to see why a message was moderated and who took the action.

### Rules and examples

- Employees need to be signed in to use the feature.
- People cannot send kudos to themselves or to an inactive account.
- A message must contain text and be no longer than 500 characters.
- Messages are plain text, so entered code or HTML will not run in the feed.
- The feed shows the newest visible messages first. It loads a small number at a time, with a button to show more.
- Hidden or removed messages should not appear in the normal feed.
- Only administrators can moderate messages. They must give a reason when hiding or removing one.
- Removing a message will hide it from users while keeping a record for moderation history.
- The form should stop accidental repeat submissions, for example by disabling the submit button while it is saving.
- The page should work on phones and computers, and show clear messages if something goes wrong.

## How it could be built

For a first version, use **Python with Flask**, an **SQLite** database, and HTML/CSS with a small amount of JavaScript. This is a simple setup for a working demonstration. The company could connect it to its normal sign-in system if the feature was later added to the real portal.

### Database tables

**Users** stores the people who can use the feature:

- `id` — unique ID for each person
- `name` — name shown on the portal
- `email` — email address
- `role` — employee or administrator
- `is_active` — whether the account can be used

**Kudos** stores each message:

- `id` — unique ID for the message
- `sender_id` — the person who sent it
- `recipient_id` — the person receiving it
- `message` — the message, up to 500 characters
- `created_at` — when it was sent
- `is_visible` — true by default; false when hidden or removed
- `moderated_by` — administrator who last changed its status
- `moderated_at` — when the administrator acted
- `moderation_reason` — why the message was hidden or removed
- `is_deleted` — marks a removed message while keeping its record

**Moderation history** keeps a record of administrator actions:

- `id` — unique ID for the action
- `kudos_id` — message that was moderated
- `admin_id` — administrator who acted
- `action` — hide, show again or remove
- `reason` — reason for the action
- `created_at` — when it happened

The user IDs connect the tables, so each kudos message can be linked to its sender and recipient.

### Main pages and routes

- The **kudos form** lets an employee find a colleague, write a message and submit it.
- The **kudos feed** shows recent visible messages, with a “Show more” option.
- The **admin page** lists messages that may need attention and lets an administrator hide, restore or remove them.

Possible web routes:

- `GET /users` — find colleagues to send kudos to
- `POST /kudos` — submit a new message
- `GET /kudos` — load recent visible messages
- `GET /admin/kudos` — view messages for moderation
- `POST /admin/kudos/<id>/moderate` — hide, restore or remove a message and save the reason

### Keeping it safe and reliable

- Check that the person is signed in and has the right role before showing or changing data.
- Get the sender from the signed-in account instead of trusting a sender ID typed into the form.
- Check the message length and recipient before saving.
- Display messages as text so they cannot run scripts in the browser.
- Keep administrator actions and reasons in the moderation history.
- Show a helpful error if the database is unavailable or the form contains invalid information.
- Do not put passwords or private keys in the code.

## Plan for building it

1. Set up the Flask app and SQLite database.
2. Add the Users, Kudos and moderation history tables.
3. Build the page where an employee chooses a colleague and writes a message.
4. Add the feed and make sure hidden messages do not appear there.
5. Add an administrator page for hiding, restoring and removing messages.
6. Test normal use and edge cases, including blank messages, messages that are too long, sending kudos to yourself, and moderation permissions.
7. Check that the page works on a phone and a computer.
8. Write simple instructions for running and testing the app.

## Approval

Status: **Waiting for review before implementation.**
