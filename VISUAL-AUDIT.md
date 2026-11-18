# Portfolio visual audit

Reviewed the live fmanrique.com homepage, Selected Projects, the two tool case studies, the checkpoint benchmark, the Incremental Replay share image, and the matching local Astro checkout before designing the article.

| Surface | Observation | Decision |
| --- | --- | --- |
| Homepage at desktop and 390 px | The serif hero, warm background, and two-column project grid establish the site's voice. At 390 px projects form a single column and links remain readable. | Keep the layout and Blog/About navigation. Use the same body typography, warm paper, and rust accent in the research article. |
| Three existing articles at both widths | The Georgia heading and 660 px prose width work on desktop. Long code wraps or scrolls inside its box at 390 px. Existing article tables remained within their wrappers. There were no embedded maps, charts, or screenshots in the bodies. | Use the same article frame, figures with captions, and a horizontally scrollable region for the detailed results table on narrow screens. |
| Incremental Replay share image | The 1200 × 630 graphic makes two numbers legible, with one contrast color per state. | Give demand, candidates, and selected hubs distinct shapes as well as colors. Keep the same extent while toggling demand representations. |
| Header and favicon | The live header used a text wordmark. The source had no icon link and the live `/favicon.ico` returned 404. | Add a small rust-colored F mark beside the wordmark and use the same square PNG at `/favicon.png` across the shared template. |

Google recommends a stable, crawlable square favicon larger than 48 × 48 and a home page with a corresponding icon link. The proposed asset is a 64 × 64 PNG. The existing robots rules allow it. [Google favicon guidance](https://developers.google.com/search/docs/appearance/favicon-in-search)
