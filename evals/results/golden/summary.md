# Golden-set evaluation (50 hand-labeled reviews)

Config: `jev-1.13.0+jev-q-tiny-v1-pack10+schema-v1+quote-v1+sent-from-intent-v1` · predictions from saved state (no model calls)

| Metric | Result |
|---|---|
| topic_agreement | 35/50 |
| intent_agreement | 45/50 |
| topic_and_intent_both | 33/50 |
| severity_exact | 36/50 |
| severity_within_1 | 49/50 |
| severity_mae | 0.3 |
| sentiment_mae | 0.305 |
| sentiment_within_0.5 | 46/50 |
| evidence_quote_exact_substring | 50/50 |
| evidence_quote_whole_text | 46/50 |
| entities_unsupported_by_text | 0 |
| missing_or_quarantined | 0 |
| ambiguous_cases_flagged_by_labeler | 0 |

## Topic confusion

| human \ predicted | access | usability | playback | downloads | catalog | billing | support | other |
|---|---|---|---|---|---|---|---|---|
| **access** | · | · | 2 | · | · | · | · | · |
| **usability** | · | 3 | · | · | · | · | · | 1 |
| **playback** | · | 2 | 4 | · | 1 | · | · | · |
| **downloads** | · | · | · | 1 | · | · | · | · |
| **catalog** | · | · | · | · | 2 | · | · | · |
| **billing** | · | 4 | · | · | · | 1 | · | · |
| **other** | · | 1 | · | · | 3 | 1 | · | 24 |

## Intent confusion

| human \ predicted | complaint | request | praise | cancellation | unclear |
|---|---|---|---|---|---|
| **complaint** | 19 | · | · | · | · |
| **request** | · | 1 | · | · | · |
| **praise** | · | · | 19 | · | 1 |
| **cancellation** | · | · | · | 1 | · |
| **unclear** | 1 | 3 | · | · | 5 |

## Severity confusion

| human \ predicted | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| **1** | 27 | 8 | · | · | · |
| **2** | · | 3 | 4 | 1 | · |
| **3** | · | · | 2 | 1 | · |
| **4** | · | · | · | 4 | · |

## needs_review as a predictor

```
{
 "flagged": 11,
 "flagged_with_topic_or_intent_error": 7,
 "unflagged": 39,
 "unflagged_with_topic_or_intent_error": 10,
 "errors_caught_by_flag": "7/17"
}
```

## Disagreements (topic, intent or severity)

| review_id | text | human t/i/s | predicted t/i/s | flagged |
|---|---|---|---|---|
| `0d4f8b48` | It's really an amazing experience with Spotify...I love it🥰 | usability/praise/1 | other/praise/1 |  |
| `991b6b3a` | Ads were okay, but limited functionality..it's just too much | billing/complaint/2 | usability/complaint/3 |  |
| `0c6ca545` | Hate this application 🤮🤮🤮🤮🤮🤮 | other/complaint/1 | other/complaint/2 |  |
| `1fc8b08f` | Duo Premium .... No ads at all! | billing/praise/1 | usability/praise/1 |  |
| `723f07de` | Update: I reached out to Spotify Support and with some help from Sarah I was able to get t | access/complaint/4 | playback/complaint/4 |  |
| `47428620` | This app is bad work | other/complaint/1 | other/complaint/2 |  |
| `fc344263` | Great... | other/praise/1 | other/unclear/2 | yes |
| `01d453b0` | I like it but god I hate it when the music Interrupts my ads | playback/complaint/2 | usability/complaint/2 |  |
| `ac6cd66d` | Lhat ng song nasa spotify | other/unclear/1 | catalog/request/1 | yes |
| `46842184` | asem, lirik nya kdang gaada kek mana?? | other/unclear/1 | catalog/request/1 | yes |
| `657f1b77` | Hate This application 👎 | other/complaint/1 | other/complaint/2 |  |
| `de48c99b` | I LOVE that I was able to put in only a few songs I like and Spotify gave me recommendatio | playback/praise/1 | catalog/praise/1 |  |
| `372d4e67` | Please ye ads ko thoda kumm Karo harr ek song ke baad ad 🙏🙄 | other/unclear/1 | usability/request/2 |  |
| `47f1406d` | Very poor updates as we cannot playback the songs and most bad updates are happening it is | playback/complaint/3 | playback/complaint/4 |  |
| `3ddb3f4e` | Deleting this App. The new update suck, we can't choose our fvrt songs after some clicks,  | billing/cancellation/2 | usability/cancellation/4 | yes |
| `16d640e9` | It's my best music app but now it's not...everything basic features is premium.... | billing/complaint/2 | billing/complaint/3 |  |
| `8cc4fad4` | I hate this app and sweden .I love islam | other/unclear/1 | other/complaint/2 |  |
| `215463ae` | What is happening with Spotify?? Recently I'm trying to play a song but it doesn't working | access/complaint/4 | playback/complaint/4 |  |
| `46c0b49f` | Are you out of your mind? This is dangerous! Listening to music in a normal volume and sud | playback/complaint/2 | usability/complaint/3 | yes |
| `283b5843` | Beth, we all got to give me a free dollar to go with 3 months, bro I can't be like | other/unclear/1 | billing/unclear/1 | yes |
| `1a41c7e1` | Worst application 👎👎👎 | other/complaint/1 | other/complaint/2 |  |
| `5fba12ea` | I find Spotify very good, it finds and play whatever music you want and also adds songs th | other/praise/1 | catalog/praise/1 |  |
| `d2f3874f` | Too expensive and the free version is pretty much unusable with constant ads... Every two  | billing/complaint/2 | usability/complaint/3 | yes |
| `99b93e31` | This update very bad for everyone.old Spotify. we all want. | other/complaint/1 | other/complaint/2 | yes |
