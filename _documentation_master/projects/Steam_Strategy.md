
##Task
1. Establish GOB's presence on Steam

##Task Objectives
1. Drive awareness for the game leveraging Steam's discovery tools
2. Acquire play testers for the game without uderming monetizatoin down the road

##Product Stages
1. Play Testing
    - get user feedback and validate product market fit
2. Beta Testing
    - Pre-launch, check for bugs and ensure game stability
3. Launch
    - Drive revenue targets

##Monetization Plan
- Game Sales: sell downloadable versions of the game
    - comes with 300 "recruit" headshots that will be randomly assigned to newly created plaeyrs in every recruitign class assimung the user does not buy any additional recruit packs.
    - Pricing
        - Varsity: $29.99: game only
        - Varsity Plus: $34.99: game + 5 recruit packs
        - All-American: $54.99: game + 5 recruit packs + one year subscription
- Recruit packs
    - Sets of 300 custom built recruits each with their own headshot and attributes
    - Pricing
        - One Pack: $2.99
        - Five Packs: $9.99
        - Twelve Packs: $19.99
- Subscription
    - Gives the user access to the live online community and special live features
    - Live PvP games, tournaments and eventually a franchise
    - User can plug their personal franchise mode results so the online community can see their results and they can be a part of user franchsie leaderboards that will track a multiude of user franchise stats like titles won, total wins, recruiting performance, coaching style and more.
    - Pricing
        - Monthly: $2.99/month
        - Annual: $29.99/year

##Questions
1. What is the recommended appraoch to the Play Test Phase?
    a. launch a downloadable game with limited features so as not to cannibalize full game sales? example: no progression beyond the first season
        - if so, how do I get user feedback on this? Or is my feedback simply the number of people who download the gmae?
        - do I get play statistics with this?
    b. launch an online version of the playtest (like I'm doing now) so I can track all usage via my Google Analytics? Does Steam allow this?
    c. something else?
2. What is the ideal order of operations for getting onto Steam and achieving my 3 objectives (play test, beta test, launch)? My first pass at a proposed plan is below.
3. What am I overlooking? What are some other best practices for succeeding on Steam?

##Order of operations -- below is my current understanding, but I need help framing this up in the right order. I'm not sure if this is correct or if I'm missing some key items.

1. Create / finish Steamworks onboarding
Create Steamworks partner account.
Sign Steam NDA and distribution agreement.
Pay Steam Direct app fee.
Complete identity, tax, and bank info.
Make sure the bank account name matches your legal/company name. Steam says onboarding requires paperwork, bank/tax info, app fee, store page, build upload, pricing, and review.
2. Create the GOB app in Steamworks
Create app: Geeked Out Basketball.
Choose game type/platforms.
Set supported OS.
Set default language.
Set developer/publisher name.
Do not overconfigure advanced features yet.
3. Prepare your test build
Make a clean Steam test build.
Confirm it launches outside your dev environment.
Remove debug/dev-only junk.
Confirm save/load works.
Confirm window/fullscreen behavior.
Confirm no broken menus.
Confirm exit/quit works.
Confirm it does not require your local backend unless intentionally online-only.
4. Upload build through SteamPipe
Install Steamworks SDK.
Configure depot/build scripts.
Upload first build.
Put it on a private/internal branch first.
Install it through Steam as a tester.
Launch it from Steam, not Cursor/local browser.
Test like a real player. Steam’s docs specifically route build uploading through SteamPipe/SDK tooling.
5. Prepare the Coming Soon store page

Minimum viable assets:

Capsule/header art
5–8 real screenshots
1 gameplay-first trailer, if ready
Short description
Long description
Tags
Genre/category
Supported languages
System requirements
Basic controller/keyboard info
AI disclosure, if any player-facing AI content is used

Do not use misleading art or cinematic fluff. Real gameplay proof matters.

6. Set pricing / release basics
Choose paid game, demo, or playtest setup.
Enter planned price, even if not launching immediately.
Pick rough release timing.
Set “Coming Soon,” not full launch.
Make sure you understand you need a public Coming Soon page for at least two weeks before release, and there is also a 30-day waiting period after paying the app fee before you can release your first titles.
7. Submit for Steam review

Submit both:

Store page review
Build review

Steam says the review process checks the game, store page, configuration, launch behavior, and harmful content, and usually takes 1–5 days.

8. After approval
Publish Coming Soon page.
Test wishlist flow.
Test community hub.
Add first Steam announcement.
Share Steam page link everywhere.
Start collecting wishlists.
Keep updating screenshots/trailer as GOB improves.