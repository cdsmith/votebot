# Electable

Electable is a Discord bot that facilitates running elections using various voting methods. It implements interactive secret ballots to ensure an easy and private voting experience. Users can cast ballots for a variety of election types and ballot formats with a simple and intuitive user interface.

## Features

### What it does

- **Multiple Voting Methods**: The intent is to implement most commonly used single-winner and multi-winner election methods.  Current support includes:
  - **Approval**: Voters approve any number of candidates. The candidate with the most approvals wins.
  - **Borda Count**: Voters rank candidates, and candidates are awarded points based on their position in the ranking. The candidate with the highest Borda count wins.
  - **Copeland**: Voters rank candidates, and the candidate who wins the most head-to-head comparisons is chosen.  This is a Condorcet-consistent method.
  - **Instant Runoff / Single Transferable Vote**: Voters rank candidates, and the candidate with the fewest first-place votes is eliminated in each round until a winner emerges. Also known as RCV ("Ranked Choice Voting"). Supports both single-winner and multi-winner elections.
  - **Kemeny-Young**: Voters rank candidates, and the ranking that agrees with the most voter pairwise preferences is chosen. This is a Condorcet-consistent method.
  - **Plurality**: Voters choose a single candidate.  The candidate with the most votes wins. Also known as FPTP ("First Past the Post").
  - **Ranked Pairs**: Voters rank candidates, and a consistent candidate ordering is chosen from the strongest pairwise preferences. This is a Condorcet-consistent method.
  - **Rivest-Shen GT**: Voters rank candidates, and the winner is chosen according to the unique probablistic strategy that maximizes the expected number of voters preferring this outcome versus any alternative. This is a Condorcet-consistent method.
  - **Score**: Voters rate candidates from 0 to 5 stars, and the candidate with the highest average score wins.
  - **STAR**: Voters rate candidates from 0 to 5 stars.  The two candidates with the highest average scores advance to a runoff, in which the candidate preferred by the most ballots wins.
  - **Tideman's Alternative Method**: Voters rank candidates.  In each round, if there are candidates not in the Smith set, they are eliminated.  Otherwise, the candidate with the fewest first-place votes is eliminated.  A winner is chosen when a candidate has a majority of first-place votes. This is a Condorcet-consistent method.

- **Private and Interactive Ballots**:  
  Users click a "Vote" button on the public election message to open a private, ephemeral ballot. They can select or rearrange their choices using Discord’s message components (buttons, selects), and submit when ready.

- **Detailed Results**:
  When the election is ended, the winner is displayed.  Optionally, detailed tabulation info is also provided to explain how the result is obtained.

- **Scheduled Elections**:
  Elections can be scheduled to end automatically at a specific date/time or after a duration. End times are displayed in each user's local timezone.

- **Election Management**:
  A unified `/electable` command provides easy access to all your elections in a channel, allowing you to create, reschedule, end, or delete elections from one interface.

### What it doesn't do (yet)

- While basic multi-winner elections are supported via STV, more advanced multi-winner methods and open party-list methods that require voters to make more than a single decision between candidates are not yet implemented.
- It doesn't look pretty.  If that's your talent, I'd be grateful for your help.
- A few little usability things are missing: sending reminders, warning if a voter fills out and doesn't submit a ballot.

## Setup

You can use this bot by simply adding it to your server (easiest) or by running your own instance.  You only need to run your own instance if you plan to make changes to the code.

### Adding to a server

To add the bot to your server, simply visit the [authorization link](https://discord.com/oauth2/authorize?client_id=1318357026493042799&permissions=2048&integration_type=0&scope=bot) in your web browser, and authorize it to join.  Once the bot has joined the server, you can use the `/election` command to begin an election, and the `/end_election` command to end it and report results.

### Running your own instance

Note that you ONLY need to run your own instance if you plan to make changes to the code.  If you just want to use the bot, you can add it to your server as described above.

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

### Managing elections with `/electable`

The `/electable` command is your one-stop interface for all election management:

```
/electable
```

This opens an ephemeral (private) interface showing:
- A list of your active elections in the current channel
- Options to create new elections
- Management controls for existing elections (reschedule, end, delete)

### Creating an election

From the `/electable` interface, click "Create New Election" and fill out:

* **Title**: A title for the election
* **Description** (optional): Additional information about the election
* **Method**: Choose from various voting methods (Plurality, IRV, Approval, etc.)
* **End Time** (optional): Schedule when the election ends automatically
  - Use relative durations: `2d` (2 days), `3h30m` (3 hours 30 minutes), `1w` (1 week)
  - Or absolute dates: `2025-12-25 14:30`
* **Candidates**: Add at least two candidates

The bot will post a public message in the channel announcing the election. Anyone can click the Vote button to cast a ballot. Ballots are private and votes can be changed until submission.

### Scheduling elections

Elections can be scheduled to end automatically by specifying an end time during setup or by using the Reschedule option. The end time is displayed in each user's local timezone as both an absolute time and a countdown. When the scheduled time is reached, the election automatically ends and results are posted.

Examples of end time formats:
- `2d` - 2 days from now
- `12h` - 12 hours from now
- `3h30m` - 3 hours and 30 minutes from now
- `2025-12-25 14:30` - Specific date and time (UTC)
- Leave the field blank to run the election until it is manually ended.

### Managing your elections

Use `/electable` to:
- **Reschedule**: Change the end time of an election
- **End Now**: Immediately end an election and show results
- **Delete**: Remove an election without showing results

## Extending the Bot

If you'd like to extend the bot with additional features, you can do so as follows:

### Implementing a new election method

To implement a new election method, define a new subclass of `Election`.  You will need to implement the following.

```python
    @abc.abstractmethod
    def name(self) -> str:
        """Return the name of the election method."""
        pass

    @abc.abstractmethod
    def blank_ballot(self) -> Ballot:
        """Return a new, empty ballot."""
        pass

    @abc.abstractmethod
    def tabulate(self) -> tuple[list[str], str]:
        """Returns tabulated results.

        The first result should be a list of winners (usually one, but multiple in case of a tie)
        The second result should be an explanation of how the winner was chosen.
        """
        pass
```

This is generally the easiest kind of extension you can make.  The code is self-contained and doesn't rely on Discord APIs or other complex systems.  You can refer to the existing `Election` subclasses for hints on implementation.

### Implementing a new ballot format

If there is no ballot format defined for the election method you want to implement, you'll need to implement a new ballot format, as well.  For this, you will write a subclass of `Ballot`.  You will need to implement the following.

```python
    @abc.abstractmethod
    def candidates_per_page(self) -> Optional[int]:
        """How many candidates can fit on a page.  If None, there is one page for all candidates."""
        pass

    @abc.abstractmethod
    def clear(self) -> None:
        """Clear all votes from the ballot."""
        pass

    @abc.abstractmethod
    def get_items(self, candidates: list[str], session_id: int) -> list[discord.ui.Item]:
        """Return a list of discord.Item objects for a page of candidates."""
        pass

    @abc.abstractmethod
    def submittable(self) -> bool:
        """Determines if the ballot is complete enough to submit."""
        pass

    @abc.abstractmethod
    def to_markdown(self) -> str:
        """Return a ballot choice in markdown."""
        pass
```

Ballot formats are typically somewhat involved, and require knowing something about the Discord API and available user interface elements.  You can refer to the existing `Ballot` subclasses for hints on implementation.  Because Discord
limits the UI elements that can be used in a message, ballots are automatically
paginated if there are more than 5 candidates.  The `candidates_per_page` method
should return the number of candidates that can fit on a single page, or `None`
if all candidates should be on a single page.

Note that you do not need to implement a new ballot format if your election method can use an existing one!  There are already ballots implemented for single-choice, multiple-choice, ranked-choice, and scored-choice elections.

## Contributing

Contributions are welcome! Whether it’s improving the UI, adding new voting methods, or refining the user experience, feel free to open issues or submit pull requests.

## License

This project is licensed under the 2-Clause BSD License