# Social Activation

## Goal

Create a system where GOB can automatically celebrate major user achievements by posting from official GOB social accounts.

Examples:

- Winning a tournament
- Scoring 100 points in a game
- Reaching a major leaderboard milestone
- Unlocking a rare achievement

The post should congratulate the user and, where possible, tag or link to their social account.

## Recommended Approach

Build this as a game achievement workflow, not as an email workflow.

Basic flow:

1. A special event happens in the game.
2. GOB detects that the event qualifies for social activation.
3. GOB creates a pending social post.
4. An admin can approve, edit, or reject the post.
5. GOB publishes the post to X and/or Facebook.
6. GOB saves the published post URL for reference.

Over time, trusted achievement types can become fully automatic.

## Tools Needed

### X

Use the X API.

GOB would connect the official GOB X account to the app and use that account to publish posts.

For user tagging, GOB should collect and verify the user's X account through OAuth. Once verified, posts can mention the user's handle.

Example:

```text
Congrats @playerhandle for winning the GOB Summer Tournament.
```

X is the best first platform for this feature because public mentions are straightforward.

### Facebook

Use the Meta/Facebook Graph API.

GOB would publish from the official GOB Facebook Page, not from a personal profile.

Facebook is more restrictive than X. It is reasonable to publish a congratulatory Page post and link to the user's GOB profile or achievement page, but direct tagging of a user's personal Facebook profile may not be reliable or available without additional Meta permissions and review.

For Facebook, design the first version around:

- Posting from the GOB Facebook Page
- Mentioning the user by GOB display name
- Linking to the GOB post, profile, or achievement page

Treat direct Facebook user tagging as a possible enhancement, not a core requirement.

### Resend

Resend should not be used to publish social posts.

Resend is useful for email notifications related to the workflow, such as:

- Notifying a user that GOB featured them
- Asking a user to opt in to public mentions
- Alerting an admin that a social post is awaiting approval

## User Account Linking

Users should be able to connect social accounts from their GOB account settings.

Recommended fields:

- Provider: X or Facebook
- Verified account ID
- Display name / handle
- Profile URL
- Whether the user allows public mentions
- Date connected

This prevents users from claiming accounts they do not own.

## Important Product Decisions

### User Consent

Users should opt in before GOB tags or links them in public posts.

Suggested setting:

```text
Allow GOB to mention me in public celebration posts.
```

### Approval Queue

Start with an admin approval queue.

This avoids accidental posts, abuse cases, bad wording, duplicate achievements, or posts about test data.

Later, certain low-risk achievement types can be auto-approved.

### Post Templates

Use controlled templates instead of fully freeform generated posts.

Example:

```text
{display_name} just scored {points} points in a GOB game.

That is a monster performance.

View the game: {gob_link}
```

For X, include the verified handle when available.

For Facebook, include the user's GOB display name and a GOB link.

## Suggested First Version

Version 1 should include:

- Milestone detection for a small set of achievements
- Connected X account support
- User opt-in for public mentions
- Pending social post table
- Admin approval screen
- X publishing from the official GOB account
- Resend email notifications for users/admins

Facebook can be added after the core workflow is stable, because Meta permissions and tagging behavior are more restrictive.

## Summary

This can be done, but it requires direct social platform integration.

Use:

- X API for X posts and user mentions
- Meta Graph API for Facebook Page posts
- Resend only for email notifications

The best first build is an opt-in, approval-based X celebration system, followed by Facebook Page posting once the workflow is proven.
