window.LABEL_SET = {
 "name": "dev_50",
 "title": "Development set (50) — used for Jev examples and threshold tuning",
 "labels": {
  "version": "labels-v1",
  "classify_from": "review_text only. Stars, likes, app version and dates are metadata, never label inputs.",
  "topic": {
   "rule": "Choose the problem with the highest supported severity. On a tie, choose the first specific problem mentioned. For a positive review, choose the first specific praised feature; general praise is `other`. Mentioning a paid plan alone does not make the topic billing.",
   "options": {
    "access": {
     "definition": "Login, signup, password or account access",
     "illustrations": [
      "keeps logging me out",
      "can't sign in with Facebook",
      "account got locked/hacked"
     ]
    },
    "usability": {
     "definition": "Navigation, controls, layout, queue/playlist management, ad interruptions",
     "illustrations": [
      "the new home screen is confusing",
      "too many ads between songs",
      "can't reorder my queue"
     ]
    },
    "playback": {
     "definition": "Playback failure, crashes, lag, connection failures, audio quality, resource use",
     "illustrations": [
      "app crashes when I open it",
      "music stops when the screen locks",
      "drains my battery"
     ]
    },
    "downloads": {
     "definition": "Downloading, saved music, offline listening, disappearing downloads",
     "illustrations": [
      "my downloaded songs vanished",
      "offline mode doesn't work on the plane"
     ]
    },
    "catalog": {
     "definition": "Missing songs/artists, search/discovery, recommendations, lyrics availability",
     "illustrations": [
      "lyrics are missing",
      "search can't find the artist",
      "recommendations are repetitive"
     ]
    },
    "billing": {
     "definition": "Price, charges, subscriptions, paywalls, premium entitlement; explicitly premium-only controls go here",
     "illustrations": [
      "charged twice this month",
      "premium didn't activate after paying",
      "can only pick songs if I pay"
     ],
     "notes": [
      "A subscription failing to activate is billing.",
      "Music crashing for a paying customer is playback, not billing."
     ]
    },
    "support": {
     "definition": "Contacting support and the support response",
     "illustrations": [
      "support never answered my email",
      "chat agent couldn't help"
     ]
    },
    "other": {
     "definition": "General praise/criticism, unrelated content, or no supported specific topic",
     "illustrations": [
      "great app",
      "worst app ever",
      "boycott slogan with no product issue"
     ]
    }
   }
  },
  "intent": {
   "rule": "Precedence when several apply: cancellation > complaint > request > praise > unclear.",
   "options": {
    "cancellation": {
     "definition": "Explicitly leaving, uninstalling, cancelling, or threatening to do so",
     "notes": [
      "Cancellation intent does not automatically raise severity."
     ]
    },
    "complaint": {
     "definition": "Negative experience, including mixed praise/criticism",
     "notes": [
      "General \"bad app\" is a complaint; do not infer a specific defect."
     ]
    },
    "request": {
     "definition": "Desired change without a reported failure"
    },
    "praise": {
     "definition": "Positive experience with no complaint"
    },
    "unclear": {
     "definition": "Bare boycott slogans, unrelated or meaningless text, or unsupported language",
     "notes": [
      "A boycott becomes complaint/cancellation only with a product complaint or explicit personal departure."
     ]
    }
   }
  },
  "severity": {
   "rule": "Rate the reported impact, not the emotion. Stars, angry language or cancellation intent alone do not establish severity. Missing context -> needs_review; do not invent impact.",
   "levels": {
    "1": "No reported problem — praise, neutral/unclear content, or a pure feature request",
    "2": "Dislike, generic criticism, minor annoyance, or a cosmetic issue; no supported functional loss",
    "3": "A degraded or restricted function; some use or workaround remains",
    "4": "A clearly blocked core task, such as inability to log in or play music",
    "5": "Explicit serious financial, privacy, or data harm; an expensive plan, a crash, or angry language alone is insufficient"
   }
  },
  "sentiment": {
   "scale": "-1.0 (very negative) to 1.0 (very positive)",
   "levels": {
    "-1.0": "very negative",
    "-0.5": "negative",
    "0.0": "neutral or mixed",
    "0.5": "positive",
    "1.0": "very positive"
   },
   "note": "Labels use these five points; Jev Score 0-4 maps to score/2 - 1."
  },
  "entities": {
   "definition": "Product features or named things the review explicitly mentions (e.g. \"shuffle\", \"lyrics\", \"downloads\", \"premium\", \"Android Auto\"). Lowercase, as written. No personal names or details. Empty list when none."
  },
  "evidence_quote": {
   "definition": "An exact, unmodified substring of review_text that supports the chosen topic/intent/severity. For a short review the whole text can be the quote."
  },
  "needs_review": {
   "definition": "true when the text is ambiguous, lacks context needed for topic or severity, is in a language the labeler cannot read confidently, or the labels are a close call."
  }
 },
 "rows": [
  {
   "review_id": "e9a7546c-7ced-4016-a7e5-bd6914783ace",
   "review_text": "love it but please for the love of god get rid of the smart shuffle thing or like, make it a separate button cuz i'm just trying to reshuffle my playlist and it makes the process very annoying",
   "source": {
    "review_id": "e9a7546c-7ced-4016-a7e5-bd6914783ace",
    "review_text": "love it but please for the love of god get rid of the smart shuffle thing or like, make it a separate button cuz i'm just trying to reshuffle my playlist and it makes the process very annoying",
    "review_rating": "4",
    "review_likes": "0",
    "app_version": "8.8.46.529",
    "review_timestamp": "2023-07-05 13:33:47"
   }
  },
  {
   "review_id": "a1a52508-1b15-478f-8582-d39dfe0df66c",
   "review_text": "I'm an account manager for a family plan, who suddenly doesn't have access to their account. I've been trying for days to login through Facebook, on every device I own, which is the only way I have ever logged in and I keep getting an error message. Should have stuck with Pandora.",
   "source": {
    "review_id": "a1a52508-1b15-478f-8582-d39dfe0df66c",
    "review_text": "I'm an account manager for a family plan, who suddenly doesn't have access to their account. I've been trying for days to login through Facebook, on every device I own, which is the only way I have ever logged in and I keep getting an error message. Should have stuck with Pandora.",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "8.7.64.478",
    "review_timestamp": "2022-09-10 02:43:57"
   }
  },
  {
   "review_id": "f24cd91b-59c0-4f9c-89e9-e8180c339344",
   "review_text": "This needs an update, I'm getting issues with playing music and everything stops working until you restart, sometimes more than once or your device itself.",
   "source": {
    "review_id": "f24cd91b-59c0-4f9c-89e9-e8180c339344",
    "review_text": "This needs an update, I'm getting issues with playing music and everything stops working until you restart, sometimes more than once or your device itself.",
    "review_rating": "3",
    "review_likes": "0",
    "app_version": "8.7.92.521",
    "review_timestamp": "2022-12-24 00:37:47"
   }
  },
  {
   "review_id": "84c09d0f-3a59-4dd8-9413-a62b934accbb",
   "review_text": "To much problem.. all the items are gone premium...",
   "source": {
    "review_id": "84c09d0f-3a59-4dd8-9413-a62b934accbb",
    "review_text": "To much problem.. all the items are gone premium...",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "8.8.76.667",
    "review_timestamp": "2023-10-29 08:16:05"
   }
  },
  {
   "review_id": "9c1607cc-6e4c-44a0-99ca-5a956bf8d382",
   "review_text": "Pathetic app now a days even it freezes and crahsed some times.. the playlist also gets scrambled... Too many bugs since last update...",
   "source": {
    "review_id": "9c1607cc-6e4c-44a0-99ca-5a956bf8d382",
    "review_text": "Pathetic app now a days even it freezes and crahsed some times.. the playlist also gets scrambled... Too many bugs since last update...",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "",
    "review_timestamp": "2023-07-05 03:37:41"
   }
  },
  {
   "review_id": "3b6d7be5-c71a-47a3-8490-76bfc48e4279",
   "review_text": "No way to escape ads. I'm a paying subscriber with the family plan and even though I'm paying more now than I did when I signed up I'm still having advertisements foisted upon me against my will. What the hell is the point of paying if I'm still going to have to listen to ads in the middle of my podcasts on top of the ones that they integrate into the podcast? I just don't see the point in paying anymore... They're being too greedy by charging me more and not removing the ads.",
   "source": {
    "review_id": "3b6d7be5-c71a-47a3-8490-76bfc48e4279",
    "review_text": "No way to escape ads. I'm a paying subscriber with the family plan and even though I'm paying more now than I did when I signed up I'm still having advertisements foisted upon me against my will. What the hell is the point of paying if I'm still going to have to listen to ads in the middle of my podcasts on top of the ones that they integrate into the podcast? I just don't see the point in paying anymore... They're being too greedy by charging me more and not removing the ads.",
    "review_rating": "2",
    "review_likes": "0",
    "app_version": "8.7.72.546",
    "review_timestamp": "2022-10-10 18:15:42"
   }
  },
  {
   "review_id": "6078b922-0b06-4f91-be0f-98346dc2c766",
   "review_text": "Can't get a true shuffle on my playlists",
   "source": {
    "review_id": "6078b922-0b06-4f91-be0f-98346dc2c766",
    "review_text": "Can't get a true shuffle on my playlists",
    "review_rating": "3",
    "review_likes": "1",
    "app_version": "8.8.16.615",
    "review_timestamp": "2023-03-13 19:46:06"
   }
  },
  {
   "review_id": "641fcc61-7cc8-416f-ba78-017ccb320595",
   "review_text": "এটা কোন অ্যাপ বলে এর মতন বেকার আকামের পৃথিবীতে দেখিনি ব্যান করা যাক এই অ্যাপটি কে",
   "source": {
    "review_id": "641fcc61-7cc8-416f-ba78-017ccb320595",
    "review_text": "এটা কোন অ্যাপ বলে এর মতন বেকার আকামের পৃথিবীতে দেখিনি ব্যান করা যাক এই অ্যাপটি কে",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "8.7.60.422",
    "review_timestamp": "2023-07-27 06:31:25"
   }
  },
  {
   "review_id": "8585f42d-9038-48d6-bf1d-b26c17c35454",
   "review_text": "Boycott",
   "source": {
    "review_id": "8585f42d-9038-48d6-bf1d-b26c17c35454",
    "review_text": "Boycott",
    "review_rating": "2",
    "review_likes": "0",
    "app_version": "",
    "review_timestamp": "2023-07-18 04:12:06"
   }
  },
  {
   "review_id": "c3fcf858-7b2f-43be-9d2d-73f481c2cba6",
   "review_text": "Hate this application 👎",
   "source": {
    "review_id": "c3fcf858-7b2f-43be-9d2d-73f481c2cba6",
    "review_text": "Hate this application 👎",
    "review_rating": "5",
    "review_likes": "0",
    "app_version": "",
    "review_timestamp": "2023-07-09 23:21:35"
   }
  },
  {
   "review_id": "688ed267-05b4-4ec6-8fb6-0fad0b326733",
   "review_text": "Still love spotify, but I've been having sm trouble w it lately. Whether it be the constant amount of ads or the fact that sometimes it just won't play music at all so I have to force it to stop and restart it.",
   "source": {
    "review_id": "688ed267-05b4-4ec6-8fb6-0fad0b326733",
    "review_text": "Still love spotify, but I've been having sm trouble w it lately. Whether it be the constant amount of ads or the fact that sometimes it just won't play music at all so I have to force it to stop and restart it.",
    "review_rating": "3",
    "review_likes": "0",
    "app_version": "8.7.68.568",
    "review_timestamp": "2023-09-20 01:31:51"
   }
  },
  {
   "review_id": "63f6de17-f734-4b3b-9944-7cfe81ed8db1",
   "review_text": "Very useful for vibing. I could listen to music without ads and flexible enough to use my phone for other agenda while the song keeps on.",
   "source": {
    "review_id": "63f6de17-f734-4b3b-9944-7cfe81ed8db1",
    "review_text": "Very useful for vibing. I could listen to music without ads and flexible enough to use my phone for other agenda while the song keeps on.",
    "review_rating": "5",
    "review_likes": "0",
    "app_version": "8.8.12.545",
    "review_timestamp": "2023-02-28 12:41:27"
   }
  },
  {
   "review_id": "006b8080-637f-497f-893a-e8b2e44f1a0c",
   "review_text": "Worst app , having bug every 7-8 days Can't search song showing no network connection even after having good network speed",
   "source": {
    "review_id": "006b8080-637f-497f-893a-e8b2e44f1a0c",
    "review_text": "Worst app , having bug every 7-8 days Can't search song showing no network connection even after having good network speed",
    "review_rating": "2",
    "review_likes": "0",
    "app_version": "8.8.32.508",
    "review_timestamp": "2023-05-19 07:21:16"
   }
  },
  {
   "review_id": "a1b8d0cf-3c46-45b3-97ef-2673cd1e3f22",
   "review_text": "Too many Ads for subscription, other wise fantastic app!",
   "source": {
    "review_id": "a1b8d0cf-3c46-45b3-97ef-2673cd1e3f22",
    "review_text": "Too many Ads for subscription, other wise fantastic app!",
    "review_rating": "4",
    "review_likes": "0",
    "app_version": "8.8.62.491",
    "review_timestamp": "2023-08-22 13:21:19"
   }
  },
  {
   "review_id": "759bb67c-54de-441a-9a0c-c75824f719b5",
   "review_text": "Very nice",
   "source": {
    "review_id": "759bb67c-54de-441a-9a0c-c75824f719b5",
    "review_text": "Very nice",
    "review_rating": "5",
    "review_likes": "0",
    "app_version": "8.8.76.667",
    "review_timestamp": "2023-10-11 06:47:39"
   }
  },
  {
   "review_id": "d6159d51-817b-4cd2-9180-d694e657d473",
   "review_text": "I boycott all Sweden app because Sweden government given permission to burn Quran Pak. And now I'm uninstalling this app.",
   "source": {
    "review_id": "d6159d51-817b-4cd2-9180-d694e657d473",
    "review_text": "I boycott all Sweden app because Sweden government given permission to burn Quran Pak. And now I'm uninstalling this app.",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "8.8.52.458",
    "review_timestamp": "2023-07-14 08:23:59"
   }
  },
  {
   "review_id": "983c5dd7-75f7-43cf-9dee-eb0f5cda9a44",
   "review_text": "Why does the music just suddenly stops playing, even when I'm on idle and not doing anything the music just suddenly stops, and I have to reopen the app to just play it again, it's so annoying especially if I'm doing something",
   "source": {
    "review_id": "983c5dd7-75f7-43cf-9dee-eb0f5cda9a44",
    "review_text": "Why does the music just suddenly stops playing, even when I'm on idle and not doing anything the music just suddenly stops, and I have to reopen the app to just play it again, it's so annoying especially if I'm doing something",
    "review_rating": "2",
    "review_likes": "0",
    "app_version": "8.8.62.491",
    "review_timestamp": "2023-08-20 06:34:20"
   }
  },
  {
   "review_id": "f1cdfbeb-6453-4804-bfca-cb330a3158e7",
   "review_text": "Uninstall All this app",
   "source": {
    "review_id": "f1cdfbeb-6453-4804-bfca-cb330a3158e7",
    "review_text": "Uninstall All this app",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "",
    "review_timestamp": "2023-07-07 10:44:11"
   }
  },
  {
   "review_id": "90614e21-3f8f-4ba1-97a8-1db8d8c7a764",
   "review_text": "I love this app but previously I logged into my old account on my laptop and then proceeded to give me that account on my phone so now I've lost my new, better account. I would appreciate a choice to toggle between users like YouTube if that's possible",
   "source": {
    "review_id": "90614e21-3f8f-4ba1-97a8-1db8d8c7a764",
    "review_text": "I love this app but previously I logged into my old account on my laptop and then proceeded to give me that account on my phone so now I've lost my new, better account. I would appreciate a choice to toggle between users like YouTube if that's possible",
    "review_rating": "4",
    "review_likes": "1",
    "app_version": "8.7.60.422",
    "review_timestamp": "2022-09-01 18:52:20"
   }
  },
  {
   "review_id": "7dcc7236-07e6-45d5-947f-e49f166c7d61",
   "review_text": "Every two weeks or so, it does seems to \"forget\" I have premium. I press on shuffle or some other premium feature, and the app says \"you've discovered a premium feature!\" and does nothing, even though I'm signed into my premium account and restart the app several times.",
   "source": {
    "review_id": "7dcc7236-07e6-45d5-947f-e49f166c7d61",
    "review_text": "Every two weeks or so, it does seems to \"forget\" I have premium. I press on shuffle or some other premium feature, and the app says \"you've discovered a premium feature!\" and does nothing, even though I'm signed into my premium account and restart the app several times.",
    "review_rating": "4",
    "review_likes": "0",
    "app_version": "8.8.50.466",
    "review_timestamp": "2023-07-07 09:40:22"
   }
  },
  {
   "review_id": "2c2fefc7-e33e-42d3-be93-6ff1243c1fbd",
   "review_text": "Always great! Even the support team is amazing!",
   "source": {
    "review_id": "2c2fefc7-e33e-42d3-be93-6ff1243c1fbd",
    "review_text": "Always great! Even the support team is amazing!",
    "review_rating": "5",
    "review_likes": "0",
    "app_version": "8.7.52.1010",
    "review_timestamp": "2022-08-06 00:21:51"
   }
  },
  {
   "review_id": "99566d17-45c3-4f4e-86f0-1bef74b8c92a",
   "review_text": "I haven't been able to use spotify for over a month because my account and playlist and pretty much everything on the mobile app does not work I'm very unsatisfied with the app and the customer support I've got with it fix your app please.",
   "source": {
    "review_id": "99566d17-45c3-4f4e-86f0-1bef74b8c92a",
    "review_text": "I haven't been able to use spotify for over a month because my account and playlist and pretty much everything on the mobile app does not work I'm very unsatisfied with the app and the customer support I've got with it fix your app please.",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "8.7.48.1058",
    "review_timestamp": "2022-07-19 08:23:23"
   }
  },
  {
   "review_id": "ff9672ef-cb0e-4740-aa89-ef5dda87ae3f",
   "review_text": "You guys want to play music we don't choose and playing ads every after a song💔",
   "source": {
    "review_id": "ff9672ef-cb0e-4740-aa89-ef5dda87ae3f",
    "review_text": "You guys want to play music we don't choose and playing ads every after a song💔",
    "review_rating": "2",
    "review_likes": "0",
    "app_version": "8.8.70.532",
    "review_timestamp": "2023-09-21 15:04:04"
   }
  },
  {
   "review_id": "f9203d5d-a629-46b0-b066-804892244365",
   "review_text": "Good app, horrible optimisation and lies. When it comes to Spotify, you don't get 30 minutes of uninterrupted listening and many have also experienced this along with 3 60 second ads in a row. On another hand, some songs refuse to play, even on wifi or if you have them downloaded, this is a big bug that needs to get fixed. I force restarted Spotify several times to get it to just work sometimes with no results. It has great selection but is just not worth it.",
   "source": {
    "review_id": "f9203d5d-a629-46b0-b066-804892244365",
    "review_text": "Good app, horrible optimisation and lies. When it comes to Spotify, you don't get 30 minutes of uninterrupted listening and many have also experienced this along with 3 60 second ads in a row. On another hand, some songs refuse to play, even on wifi or if you have them downloaded, this is a big bug that needs to get fixed. I force restarted Spotify several times to get it to just work sometimes with no results. It has great selection but is just not worth it.",
    "review_rating": "1",
    "review_likes": "34",
    "app_version": "8.7.82.94",
    "review_timestamp": "2022-11-15 23:56:43"
   }
  },
  {
   "review_id": "dd8818a2-f08c-465a-b77b-4cab4bf17b6d",
   "review_text": "I know Spotify want money in exchange of premium but dont give too much pressure on users acctualy it take premium to play song otherwise purchase premium or listen it tomorrow that's unfair now i am deleting this app their are many much app for music listening that doesn't have this level of non sense",
   "source": {
    "review_id": "dd8818a2-f08c-465a-b77b-4cab4bf17b6d",
    "review_text": "I know Spotify want money in exchange of premium but dont give too much pressure on users acctualy it take premium to play song otherwise purchase premium or listen it tomorrow that's unfair now i am deleting this app their are many much app for music listening that doesn't have this level of non sense",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "",
    "review_timestamp": "2023-11-07 14:52:47"
   }
  },
  {
   "review_id": "932efad7-bc7a-4ba3-8f1f-827279f0ec37",
   "review_text": "Great to download music and make playlists that can be used when I'm offline.",
   "source": {
    "review_id": "932efad7-bc7a-4ba3-8f1f-827279f0ec37",
    "review_text": "Great to download music and make playlists that can be used when I'm offline.",
    "review_rating": "5",
    "review_likes": "0",
    "app_version": "8.8.0.347",
    "review_timestamp": "2023-01-20 13:23:52"
   }
  },
  {
   "review_id": "10357057-1b81-436b-b542-bb20aff3b6fe",
   "review_text": "Thik hi hai",
   "source": {
    "review_id": "10357057-1b81-436b-b542-bb20aff3b6fe",
    "review_text": "Thik hi hai",
    "review_rating": "5",
    "review_likes": "0",
    "app_version": "",
    "review_timestamp": "2022-11-24 03:51:32"
   }
  },
  {
   "review_id": "1d92f231-b70e-4423-9699-912776b17dca",
   "review_text": "My app doesn't want to work and I can't search anything",
   "source": {
    "review_id": "1d92f231-b70e-4423-9699-912776b17dca",
    "review_text": "My app doesn't want to work and I can't search anything",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "8.7.64.478",
    "review_timestamp": "2022-09-12 18:28:04"
   }
  },
  {
   "review_id": "2fd0d227-3466-4f6f-ad32-a2d5e614a7ea",
   "review_text": "I found a song that I never heard before. Accidentally hit the \"minus\" sign or the \"hide\" button....cant remeber the song. Can't find it in recently played. Can't find it period. I did the \"show hidden songs\" in play back > settings feature...cant find the song. I spent HOURS I mean HOURS!!!!! trying to find this song.....cant find it. customer support was trash. Chatting with someone who just copy pastes the same trash over and over is not helpful.",
   "source": {
    "review_id": "2fd0d227-3466-4f6f-ad32-a2d5e614a7ea",
    "review_text": "I found a song that I never heard before. Accidentally hit the \"minus\" sign or the \"hide\" button....cant remeber the song. Can't find it in recently played. Can't find it period. I did the \"show hidden songs\" in play back > settings feature...cant find the song. I spent HOURS I mean HOURS!!!!! trying to find this song.....cant find it. customer support was trash. Chatting with someone who just copy pastes the same trash over and over is not helpful.",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "8.5.76.962",
    "review_timestamp": "2022-06-05 02:59:11"
   }
  },
  {
   "review_id": "3d75f76e-9be9-4062-8964-6fd468043902",
   "review_text": "I've been using Spotify for 5 years. It's amazing at first. But after every new update they'll delete a feature. It's a bit annoying at some point. But in the latest update, You need to buy premium even if you want to play it from your favourite part (the basic feature for any music app). I mean, isn't that a bit extreme?",
   "source": {
    "review_id": "3d75f76e-9be9-4062-8964-6fd468043902",
    "review_text": "I've been using Spotify for 5 years. It's amazing at first. But after every new update they'll delete a feature. It's a bit annoying at some point. But in the latest update, You need to buy premium even if you want to play it from your favourite part (the basic feature for any music app). I mean, isn't that a bit extreme?",
    "review_rating": "1",
    "review_likes": "1",
    "app_version": "8.8.78.587",
    "review_timestamp": "2023-10-18 18:57:23"
   }
  },
  {
   "review_id": "772248c9-549d-411f-b81d-55aac25e30a7",
   "review_text": "The smart shuffle has to either go or be able to turned off completely I do not like it Other then that I love using Spotify",
   "source": {
    "review_id": "772248c9-549d-411f-b81d-55aac25e30a7",
    "review_text": "The smart shuffle has to either go or be able to turned off completely I do not like it Other then that I love using Spotify",
    "review_rating": "5",
    "review_likes": "0",
    "app_version": "8.8.54.481",
    "review_timestamp": "2023-07-22 23:17:01"
   }
  },
  {
   "review_id": "be3d80bd-cfa5-4e59-85c7-60a3c7467f7b",
   "review_text": "So no support for the video podcast in Nigeria. Sad",
   "source": {
    "review_id": "be3d80bd-cfa5-4e59-85c7-60a3c7467f7b",
    "review_text": "So no support for the video podcast in Nigeria. Sad",
    "review_rating": "4",
    "review_likes": "0",
    "app_version": "8.7.76.359",
    "review_timestamp": "2022-11-08 02:33:54"
   }
  },
  {
   "review_id": "fadff833-9cce-4d77-a58a-7a2e06cd0896",
   "review_text": "Stop burning quran",
   "source": {
    "review_id": "fadff833-9cce-4d77-a58a-7a2e06cd0896",
    "review_text": "Stop burning quran",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "",
    "review_timestamp": "2023-07-17 17:44:07"
   }
  },
  {
   "review_id": "97c57930-0ead-4e3c-96ad-efda13654871",
   "review_text": "We can't even go forward or backward of the lyrics . Very irritating at the beginning it was very good day by day the app is getting worse.",
   "source": {
    "review_id": "97c57930-0ead-4e3c-96ad-efda13654871",
    "review_text": "We can't even go forward or backward of the lyrics . Very irritating at the beginning it was very good day by day the app is getting worse.",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "8.8.68.565",
    "review_timestamp": "2023-09-11 12:03:07"
   }
  },
  {
   "review_id": "3694cbca-4c67-4afb-b40c-57d2454134ba",
   "review_text": "Trash app. Unusable without subscription",
   "source": {
    "review_id": "3694cbca-4c67-4afb-b40c-57d2454134ba",
    "review_text": "Trash app. Unusable without subscription",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "8.7.32.1554",
    "review_timestamp": "2022-05-24 14:42:38"
   }
  },
  {
   "review_id": "5feca8dd-8bfb-453f-9b05-6c37c4b551b8",
   "review_text": "Really amazed how Spotify can source very similar tracks to the one you've just selected ie Spotify radio. The play lists generated are good as you find new artists that create similar music to the one you like. The adds are a bit annoying as their music is louder or beatier especially if your chilling out! It would make sense to get premium if one can afford it. Thanks though for the free music in the mean time!!!",
   "source": {
    "review_id": "5feca8dd-8bfb-453f-9b05-6c37c4b551b8",
    "review_text": "Really amazed how Spotify can source very similar tracks to the one you've just selected ie Spotify radio. The play lists generated are good as you find new artists that create similar music to the one you like. The adds are a bit annoying as their music is louder or beatier especially if your chilling out! It would make sense to get premium if one can afford it. Thanks though for the free music in the mean time!!!",
    "review_rating": "5",
    "review_likes": "2",
    "app_version": "8.8.50.466",
    "review_timestamp": "2023-07-07 07:08:05"
   }
  },
  {
   "review_id": "2ae245b7-9a18-4233-a6f9-b1d955d8a583",
   "review_text": "App was good earlier, but recently i am facing problem while login in to the app not good at allthis thing.",
   "source": {
    "review_id": "2ae245b7-9a18-4233-a6f9-b1d955d8a583",
    "review_text": "App was good earlier, but recently i am facing problem while login in to the app not good at allthis thing.",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "8.8.0.347",
    "review_timestamp": "2023-01-14 05:54:19"
   }
  },
  {
   "review_id": "78ccefd8-3987-4dc0-9539-153f32c1db90",
   "review_text": "Having spotify without premium is good for what it is, with a wide selection of music to listen to. The ads are ads (annoying) and you only get 3 skips during a playlist, which i think is very annoying. With premium you can skip without limits, play music without ads and download songs to play offline, which is nice of course but i just dont see the purpose to pay for these simple mechanics.",
   "source": {
    "review_id": "78ccefd8-3987-4dc0-9539-153f32c1db90",
    "review_text": "Having spotify without premium is good for what it is, with a wide selection of music to listen to. The ads are ads (annoying) and you only get 3 skips during a playlist, which i think is very annoying. With premium you can skip without limits, play music without ads and download songs to play offline, which is nice of course but i just dont see the purpose to pay for these simple mechanics.",
    "review_rating": "3",
    "review_likes": "0",
    "app_version": "",
    "review_timestamp": "2022-09-15 17:22:44"
   }
  },
  {
   "review_id": "5349a2a5-20ba-46d3-821c-c6ebeb45bc80",
   "review_text": "All in one",
   "source": {
    "review_id": "5349a2a5-20ba-46d3-821c-c6ebeb45bc80",
    "review_text": "All in one",
    "review_rating": "5",
    "review_likes": "0",
    "app_version": "8.8.16.615",
    "review_timestamp": "2023-03-15 17:05:06"
   }
  },
  {
   "review_id": "db3c28f0-9c0e-4658-a0f2-eab69f540cd0",
   "review_text": "Spotify app not downloading ok but not 🚫",
   "source": {
    "review_id": "db3c28f0-9c0e-4658-a0f2-eab69f540cd0",
    "review_text": "Spotify app not downloading ok but not 🚫",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "",
    "review_timestamp": "2023-07-10 17:05:24"
   }
  },
  {
   "review_id": "eb5852f2-a9d2-4c12-bc2e-807c7a1b0244",
   "review_text": "اسوء برنامج مشغل صوتيات بمعني ادفع واشترك بفلوس عشان تسمع كويس غير كده هتلاقي اسوء تجربه",
   "source": {
    "review_id": "eb5852f2-a9d2-4c12-bc2e-807c7a1b0244",
    "review_text": "اسوء برنامج مشغل صوتيات بمعني ادفع واشترك بفلوس عشان تسمع كويس غير كده هتلاقي اسوء تجربه",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "",
    "review_timestamp": "2022-08-28 00:32:01"
   }
  },
  {
   "review_id": "f29e8bfd-7773-4f4e-8863-6d829fc6985f",
   "review_text": "I noticed the lyrics section is a bit unmanaged, especially on the 'singles & EP' and 'compilation' section. Instead of the lyrics moving forward as the song progress, it stays stagnant and more often has wrong lyrics. It says, \"the lyrics are not sync yet\" and I saw that like a year ago and it is still not synced. Also, there is no option where we can sort out the song arrangement list on our \"liked\" music section. Please, check on this one devs! Have the day ya'll deserve!",
   "source": {
    "review_id": "f29e8bfd-7773-4f4e-8863-6d829fc6985f",
    "review_text": "I noticed the lyrics section is a bit unmanaged, especially on the 'singles & EP' and 'compilation' section. Instead of the lyrics moving forward as the song progress, it stays stagnant and more often has wrong lyrics. It says, \"the lyrics are not sync yet\" and I saw that like a year ago and it is still not synced. Also, there is no option where we can sort out the song arrangement list on our \"liked\" music section. Please, check on this one devs! Have the day ya'll deserve!",
    "review_rating": "3",
    "review_likes": "0",
    "app_version": "",
    "review_timestamp": "2023-09-05 00:57:06"
   }
  },
  {
   "review_id": "116b523e-cf0d-4278-8caf-3c5a7cc41245",
   "review_text": "Even for playing a song, it is asking for premium... This is why i am uninstalling the app..this is 😡 upset user",
   "source": {
    "review_id": "116b523e-cf0d-4278-8caf-3c5a7cc41245",
    "review_text": "Even for playing a song, it is asking for premium... This is why i am uninstalling the app..this is 😡 upset user",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "8.8.36.522",
    "review_timestamp": "2023-05-25 13:31:28"
   }
  },
  {
   "review_id": "5014576b-fe43-437a-a951-0f66c978ed04",
   "review_text": "Leider wird mir jedes Mal, wenn ich den Podcast \"Hobbylos\" höre, eine längere Werbung geschaltet. Das ist sehr ärgerlich, da ich den Podcast immer zum Einschlafen höre und ich von dieser aufdringlichen Werbung gestört werde. Des Weiteren bezahle ich monatlich 14€ und erwarte daher, keine Werbung zu erhalten. Bitte beheben Sie dieses Problem.",
   "source": {
    "review_id": "5014576b-fe43-437a-a951-0f66c978ed04",
    "review_text": "Leider wird mir jedes Mal, wenn ich den Podcast \"Hobbylos\" höre, eine längere Werbung geschaltet. Das ist sehr ärgerlich, da ich den Podcast immer zum Einschlafen höre und ich von dieser aufdringlichen Werbung gestört werde. Des Weiteren bezahle ich monatlich 14€ und erwarte daher, keine Werbung zu erhalten. Bitte beheben Sie dieses Problem.",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "8.8.62.491",
    "review_timestamp": "2023-08-23 12:10:37"
   }
  },
  {
   "review_id": "e1fe3794-beda-4039-bfe4-c7b61bb8e95b",
   "review_text": "Used this paid app for years. It's company now let it fall into a whimpering reduction of it's former self. Celebrate more bugs than an ant hill, rejoice with more glitches than the Matrix. The support for current android systems is laughable. I open my app, where is the player?, might as well force stop it again for the 7th time this morning in hopes that it works. Oh no, don't worry Spotify, I don't mind taking off my welding PPE to restart your garbage app again, I got this.",
   "source": {
    "review_id": "e1fe3794-beda-4039-bfe4-c7b61bb8e95b",
    "review_text": "Used this paid app for years. It's company now let it fall into a whimpering reduction of it's former self. Celebrate more bugs than an ant hill, rejoice with more glitches than the Matrix. The support for current android systems is laughable. I open my app, where is the player?, might as well force stop it again for the 7th time this morning in hopes that it works. Oh no, don't worry Spotify, I don't mind taking off my welding PPE to restart your garbage app again, I got this.",
    "review_rating": "1",
    "review_likes": "0",
    "app_version": "8.7.34.1312",
    "review_timestamp": "2022-05-29 00:16:54"
   }
  },
  {
   "review_id": "84b770bb-1d86-4d4b-99af-4e9dd04c0b3d",
   "review_text": "Good app. Highly recommended",
   "source": {
    "review_id": "84b770bb-1d86-4d4b-99af-4e9dd04c0b3d",
    "review_text": "Good app. Highly recommended",
    "review_rating": "5",
    "review_likes": "0",
    "app_version": "8.7.76.359",
    "review_timestamp": "2022-11-06 09:50:39"
   }
  },
  {
   "review_id": "48a33ded-2772-485b-9402-9e27b6c2054c",
   "review_text": "^This is the proper way to have a pay wall system. Great app and doesn't have any problems. Still using it after all these years. Absolutely would recommend",
   "source": {
    "review_id": "48a33ded-2772-485b-9402-9e27b6c2054c",
    "review_text": "^This is the proper way to have a pay wall system. Great app and doesn't have any problems. Still using it after all these years. Absolutely would recommend",
    "review_rating": "5",
    "review_likes": "0",
    "app_version": "8.8.14.575",
    "review_timestamp": "2023-03-10 21:28:18"
   }
  },
  {
   "review_id": "71a7bde2-96c5-4c95-9fa5-19ecae208b06",
   "review_text": "I don't like the limited skips feature other than that it's good",
   "source": {
    "review_id": "71a7bde2-96c5-4c95-9fa5-19ecae208b06",
    "review_text": "I don't like the limited skips feature other than that it's good",
    "review_rating": "4",
    "review_likes": "0",
    "app_version": "",
    "review_timestamp": "2022-12-27 21:57:19"
   }
  },
  {
   "review_id": "51573c5e-96ba-4e82-a058-d0ec0a8c9e2c",
   "review_text": "So many problems. Keeps playing the same song every 3rd song will be a repeat of one I have just listened to. Keep freezing and crashing and Spotify just don't care seem to be getting worse then better thinking about finding a different place to listen to music hell even youtube with all the ads is better then this. I have contacted support for Spotify so many times and the problems still happen.... not worth the price i am paying for premium",
   "source": {
    "review_id": "51573c5e-96ba-4e82-a058-d0ec0a8c9e2c",
    "review_text": "So many problems. Keeps playing the same song every 3rd song will be a repeat of one I have just listened to. Keep freezing and crashing and Spotify just don't care seem to be getting worse then better thinking about finding a different place to listen to music hell even youtube with all the ads is better then this. I have contacted support for Spotify so many times and the problems still happen.... not worth the price i am paying for premium",
    "review_rating": "1",
    "review_likes": "1",
    "app_version": "8.8.40.470",
    "review_timestamp": "2023-06-10 12:45:21"
   }
  },
  {
   "review_id": "2e2b057a-525f-4864-9ea2-4b875eb1d681",
   "review_text": "Only problem is ads",
   "source": {
    "review_id": "2e2b057a-525f-4864-9ea2-4b875eb1d681",
    "review_text": "Only problem is ads",
    "review_rating": "5",
    "review_likes": "0",
    "app_version": "8.8.58.473",
    "review_timestamp": "2023-08-21 17:18:40"
   }
  }
 ]
};
