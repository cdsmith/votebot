# Discord Voting Bot

This is a Discord bot that facilitates running elections using various voting methods. It implements interactive secret ballots to ensure an easy and private voting experience. Users can cast ballots for a variety of election types and ballot formats with a simple and intuitive user interface.

## Features

### What it does

- **Multiple Voting Methods**: The intent is to implement most commonly used single-winner and multi-winner election methods.  Current support includes:
  - **Plurality**: Voters choose a single candidate.
  - **Approval**: Voters approve any number of candidates.
  - **Copeland**: Voters rank candidates, and the candidate who wins the most head-to-head comparisons is chosen.  This gives a Condorcet-consistent result.
  - **Score**: Voters rate candidates from 0 to 5 stars, and the candidate with the highest average score wins.
  - **STAR**: Voters rate candidates from 0 to 5 stars.  The two candidates with the highest average scores advance to a runoff, in which the candidate preferred by the most ballots wins.

- **Private and Interactive Ballots**:  
  Users click a "Vote" button on the public election message to open a private, ephemeral ballot. They can select or rearrange their choices using Discord’s message components (buttons, selects), and submit when ready.

- **Detailed Results**:  
  When the election is ended, the winner is displayed.  Optionally, detailed tabulation info is also provided to explain how the result is obtained.

### What it doesn't do

- Most notably, there is **no persistence**.  This is currently only suitable for short-term votes on the order of a few minutes.  If the bot software is restarted for any reason, all data is lost and you'll need to restart your votes.  I do intend to fix this, but not yet.
- The selection of voting methods is currently incomplete.  I've only implemented enough to validate the overall approach.
- It doesn't look pretty.  If that's your talent, I'd be grateful for your help.
- A bunch of little usability things are missing.  It can't schedule the end of the election and automatically end it at the right time.  It won't send reminders when the election is ending soon.  It won't warn you if you forget to submit your ballot after filling it out, or if you try to end an election when people have unsubmitted ballots.  It doesn't tell you how many people have voted so far.
- It doesn't catch and report errors nicely, and is almost certainly missing all sorts of validation.

## Setup

1. **Clone the repository**:
   ```bash
   git clone git@github.com:cdsmith/votebot.git
   cd votebot
   ```
2. **Install Dependencies**:
   Ensure you have Python 3.10+ and pip installed.  Then run:
   ```bash
   pip install -r requirements.txt
   ```
3. **Create a Discord Application and Bot User**:
   * Go to the Discord Developer Portal.
   * Create a new application and add a Bot user.
   * Copy the Bot Token from the Developer Portal.
4. **Set environment variables**:
   Create a `.env` file in the project directory, and:
   ```env
   DISCORD_TOKEN=your-token-here
   ```
   Of course, use the token you copied in the previous step in place of `your-token-here`.
5. **Run the bot**:
   ```bash
   python bot.py
   ```
   If successful, you should see
   ```
   YourBotName#XXXX has connected to Discord!
   ```
6. **Invite the bot to your server**:
   * In the Discord Developer Portal's OAuth2 tab, select the `bot` and `applications.commands` scopes.
   * Copy the generated invite link and open it in a browser.
   * Authorize the bot to join your server.

## Usage

### Starting an election

Use the `/election` command to start an election.

```
/election method:<method> title:<title> description:<description> candidates:<candidates>
```

* `method` is the name of a voting method.  Choose from the list offered in the UI.
* `title` is a title for the election.
* `description` is an optional description giving more information about the election.
* `candidates` is a comma-separated list of candidates.  There must be at least two candidates to hold an election.

The bot will post a public message in the channel announcing the election.  Anyone can click the Vote button on this message to cast a ballot.  Ballots are private interactions and are not visible to other users.  Votes are not finalized until the user submits their vote, and only the last submitted ballot from each user will count.

### Ending an election

Currently, elections run until they are manually ended.  When you're ready to tally the results, issue this command:

```
/end_election details:<true or false>
```

A message will be sent announcing the winner, as well as (if requested) explaining the tabulation process that led to the selection of that winner.

## Extending the Bot

This bot is a one-day project, so it's lacking a number of features.  If you'd like to extend it, you can do so as follows:

### Implementing a new election method

To implement a new election method, define a new subclass of `Election`.  You will need to implement the following.

```python
    @abc.abstractmethod
    def blank_ballot(self) -> Ballot:
        """Return a new, empty ballot."""
        pass

    @abc.abstractmethod
    def get_winners(self) -> list[str]:
        """Return list of winners (usually one, but multiple in case of a tie)."""
        pass

    @abc.abstractmethod
    def get_tabulation_details(self) -> str:
        """Return an explanation of how the winner was computed."""
        pass
```

This is generally the easiest kind of extension you can make.

### Implementing a new ballot format

If there is no ballot format defined for the election method you want to implement, you'll need to implement a new ballot format, as well.  For this, you will write a subclass of `Ballot`.  You will need to implement the following.

```python
    @abc.abstractmethod
    def copy(self) -> "Ballot":
        """Return a copy of the ballot.  Mutable fields should be copied."""
        pass

    @abc.abstractmethod
    def render_interim(self, session_id: int) -> Dict[str, Any]:
        """Return a dictionary representation of the ballot as Discord message fields."""
        pass

    @abc.abstractmethod
    def render_submitted(self) -> Dict[str, Any]:
        """Return a dictionary representation of the ballot as Discord message fields."""
        pass
```

Ballot formats are typically somewhat involved, and require knowing something about the Discord API and available user interface elements.  You can refer to the existing `Ballot` subclasses for hints on implementation.

Note that you do not need to implement a new ballot format if your election method can use an existing one!  There are already ballots implemented for single-choice, multiple-choice, ranked-choice, and scored-choice elections.

## Contributing

Contributions are welcome! Whether it’s improving the UI, adding new voting methods, or refining the user experience, feel free to open issues or submit pull requests.

## License

This project is licensed under the 2-Clause BSD License