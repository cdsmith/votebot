# Privacy Policy

*Last updated: September 2, 2026*

Electable stores what it needs to run an election and count the votes, then deletes it when the election ends. This policy covers the public instance. Anyone can run their own copy from the source code, and this policy does not apply to those.

## What is collected

**Personal information.** The only identifier the bot keeps is your numeric Discord user ID, and only while you are participating in an open election, either as a voter or as its creator. The bot does not collect names, usernames, email addresses, IP addresses, passwords, or anything else that identifies you.

**Your ballot.** While an election is open, the bot stores each voter's ballot alongside their user ID. This is what enforces one vote per person and lets you change your vote before the election ends. Ballots are private: no one, including the election creator or the maintainer, looks at who voted or how.

**Election content.** Titles, descriptions, and candidate names are written by whoever creates the election, and are stored along with the settings needed to run it. This content is already visible to everyone in the channel.

**Aggregate results.** When an election ends, the bot posts totals and tallies to the channel. These are not tied to any voter. In an election with very few voters, it may be possible to infer individual votes from the totals.

## How it is used and who can see it

Data is used only to run elections. There is no analytics, advertising, or profiling, and data is not sold or shared with anyone for their own use.

The bot runs on a single cloud-hosted server, so the hosting provider has the same operational access to the data that any host has. The bot also runs on Discord, and Discord sees everything the bot does. Discord's handling of your data is covered by [Discord's Privacy Policy](https://discord.com/privacy).

## Retention

When an election ends or is deleted, the election and every ballot in it are deleted. There is no fixed time limit while an election is open. Nothing about you remains afterward except the results message in your Discord channel, which is under your server's control like any other message.

## Your choices

- **Change your vote:** click the Vote button again any time before the election ends.
- **Delete an election:** if you created it, run `/electable` and choose Delete. This removes the election and every ballot in it.
- **Stop all data collection:** remove the bot from your server. Existing data is deleted as those elections close.

## Contact

Open an issue at [github.com/cdsmith/votebot](https://github.com/cdsmith/votebot).
