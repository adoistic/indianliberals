# Indian Liberals — Visual Asset Manifest

Scraped from https://indianliberals.in on 2026-05-16. Source is the existing WordPress site. All files preserved at full resolution where available (size suffixes like `-194x186` stripped to get originals).

## Folder structure

```
assets/
├── brand/                          # Indian Liberals brand identity
│   ├── brand-mark-crane.png        # The origami crane brand mark (master)
│   ├── logo.png                    # Header wordmark (crane + "Indian Liberals" + tagline)
│   ├── favicon-32.png              # 32×32 favicon
│   ├── favicon-180.png             # 180×180 (apple-touch-icon)
│   ├── favicon-192.png             # 192×192 (android)
│   ├── favicon-270.png             # 270×270 (MS tile)
│   ├── favicon-512.png             # 512×512 master (same image as brand-mark-crane.png)
│   └── related-ccs-projects/       # NOT IL brand — sibling CCS initiatives
│       ├── ccs-parent-org-logo.png         # Centre for Civil Society
│       ├── spontaneous-order-banner.png    # Substack federated content source
│       └── azadi-me-logo.png               # CCS Azadi.me initiative
├── thinkers/
│   ├── caricatures/                # Hand-drawn historical thinkers (4 individuals)
│   │   ├── a-d-shroff.{webp,png,jpg}
│   │   ├── m-r-pai.{webp,png,jpg}
│   │   ├── s-v-raju.{webp,png,jpg}
│   │   ├── s-v-raju-2025.webp      # Newer 2025/09 variant
│   │   └── raja-ram-mohan-roy.{webp,png,jpg}
│   ├── ring-portraits/             # Photo + yellow ring backdrop (3 contemporary thinkers)
│   │   ├── arun-shourie.webp
│   │   ├── christopher-lingle.webp
│   │   └── tom-g-palmer.webp
│   └── photos/                     # Listing-page photo portraits (13 thinkers)
│       ├── a-d-shroff.png
│       ├── b-r-shenoy.jpg
│       ├── c-rajagopalachari.jpg              # Rajaji
│       ├── d-r-pendse.png
│       ├── gopal-krishna-gokhale.jpeg
│       ├── gopal-krishna-gokhale-alt.jpg
│       ├── m-r-pai.jpg
│       ├── minoo-masani.jpg
│       ├── nani-palkhivala.jpg
│       ├── ramabai-pandita.jpg                # Pandita Ramabai
│       ├── s-v-raju.jpg
│       ├── s-v-raju-original.jpg              # Pre-crop original
│       ├── sauvik-chakraverti.jpg
│       ├── sharad-joshi.jpg                   # Sharad Anantrao Joshi
│       └── sudha-r-shenoy.jpg
└── _raw_pages/                     # Scraped HTML for reference / re-extraction
    ├── 25-visionaries.html
    ├── contributors.html
    ├── indian-liberals.html
    ├── indian_liberals-api.json    # WP REST custom-post-type listing
    ├── indian_liberals-sitemap.xml
    ├── introduction-to-indian-liberals.html
    ├── introduction-to-indian-liberals-2.html
    ├── page-sitemap.xml
    ├── profile-a-d-shroff.html
    ├── profile-m-r-pai.html
    ├── profile-raja-ram-mohan-roy.html
    └── profile-s-v-raju.html
```

## Visual language findings

The current site has a more deliberate visual identity than its WordPress execution suggests. Key observations for the rebuild design system:

### Brand mark
- **The crane** (`brand-mark-crane.png` / `favicon-512.png`): origami-style bird in the **Indian tricolor** — saffron orange beak, slate grey body, deep green legs and wing-tip outline. This is the actual brand symbol; everything else derives from it.
- **Wordmark** (`logo.png`): "Indian Liberals" set in a humanist sans-serif, with the tagline "An Online Archive of Indian Liberal Works" below. The crane appears as a small mark to the left.

### Colour palette (inferred from assets)
- **Saffron / orange** — from the crane's beak and tricolor accent (estimate: ~#E8762C)
- **Slate grey / charcoal** — primary structural colour from the crane body (estimate: ~#5B5B5B)
- **Deep green** — from the crane's legs and tricolor accent (estimate: ~#2D7A3E)
- **Warm yellow / gold** — secondary accent used in `ring-portraits/` (estimate: ~#F2B41E)
- White background throughout

**Note:** Exact hex values should be sampled programmatically from the asset files in /plan-design-review. The estimates above are eyeball-level approximations.

### Thinker treatment patterns
The site uses **two distinct visual treatments** for thinker portraits, applied by category:

1. **Hand-drawn caricature** — used for historical Indian thinkers whose photographs may not exist in high quality or who deserve elevated visual treatment as canonical figures of the tradition. Stylized ink-and-watercolor portraits, transparent background.
   - Currently exists for: A. D. Shroff, M. R. Pai, S. V. Raju, Raja Ram Mohan Roy (4 individuals)
   - Conspicuously missing: Rajaji, Masani, Shenoy, Palkhivala, Gokhale, Mithan Tata Lam, Janaki Ammal, Muthulakshmi Reddi, Sharad Joshi, D. R. Pendse, Sudha Shenoy, Sauvik Chakraverti, Ramabai Pandita

2. **Photo with yellow ring backdrop** — used for contemporary thinkers (living or recently deceased). Existing photo composited onto a yellow ring/halo.
   - Currently exists for: Arun Shourie, Christopher Lingle, Tom G. Palmer

3. **Photo portraits** (in `/photos/`) — older listing-page thumbnails for the 13 thinkers who don't yet have caricatures. These are placeholder-quality and should be considered raw source material, not finished assets.

### Implications for the rebuild design system
- The crane and tricolor palette transfer directly. Lock them in /plan-design-review.
- The caricature treatment is the project's strongest visual asset. The remaining ~9 thinkers without caricatures represent a real gap — either commission new caricatures, or accept the photo portraits in `/photos/` as v1, or use the ring-portrait treatment for living thinkers and the photo as-is for historical thinkers whose caricatures don't exist yet.
- This is a /plan-design-review question, not a v1 build-time decision.

## What's not here

The scrape covered the public-facing pages plus the WP REST media library (158 entries). Things deliberately not downloaded:

- Periodical cover images (Indian Libertarian, Freedom First, etc.) — separate scrape if needed
- Banner / hero images from the homepage (`/wp-content/uploads/2025/09/banner1-scaled.jpg` etc.)
- PDF primary works — Siraj has these locally per the office-hours conversation
- Hindi/Gujarati regional-literature page assets

Re-run the scrape with broader scope if any of these are needed for v1.

## Provenance

Each filename's underlying source URL is the original WordPress media URL. Mapping (canonical local → upstream):

### Brand
| Local | Source |
|---|---|
| `brand/logo.png` | `https://indianliberals.in/wp-content/uploads/2020/10/indian-liberals-logo.png` |
| `brand/brand-mark-crane.png` | `https://indianliberals.in/wp-content/uploads/2020/12/cropped-IL-Favicon-512x512px-32x32.png` *(rendered at master resolution)* |
| `brand/favicon-{32,180,192,270,512}.png` | `https://indianliberals.in/wp-content/uploads/2020/12/cropped-IL-Favicon-512x512px-{32x32,180x180,192x192,270x270,512x512}.png` |
| `brand/related-ccs-projects/ccs-parent-org-logo.png` | `https://indianliberals.in/wp-content/uploads/2022/10/ccs-logo-nov2017.png` |
| `brand/related-ccs-projects/spontaneous-order-banner.png` | `https://indianliberals.in/wp-content/uploads/2022/10/Untitled-10.png` |
| `brand/related-ccs-projects/azadi-me-logo.png` | `https://indianliberals.in/wp-content/uploads/2022/10/logo_5.png` |

### Caricatures
| Local | Source |
|---|---|
| `thinkers/caricatures/a-d-shroff.{webp,png,jpg}` | `https://indianliberals.in/wp-content/uploads/2022/11/AD-SHROFF.{webp,png,jpg}` |
| `thinkers/caricatures/m-r-pai.{webp,png,jpg}` | `https://indianliberals.in/wp-content/uploads/2022/11/MR-PAI.{webp,png,jpg}` |
| `thinkers/caricatures/s-v-raju.{webp,png,jpg}` | `https://indianliberals.in/wp-content/uploads/2022/11/SV-RAJU.{webp,png,jpg}` |
| `thinkers/caricatures/s-v-raju-2025.webp` | `https://indianliberals.in/wp-content/uploads/2025/09/SV-RAJU.webp` |
| `thinkers/caricatures/raja-ram-mohan-roy.webp` | `https://indianliberals.in/wp-content/uploads/2022/11/RAJA-MOHAN-1.webp` |
| `thinkers/caricatures/raja-ram-mohan-roy.png` | `https://indianliberals.in/wp-content/uploads/2022/11/RAJA-MOHAN.png` |
| `thinkers/caricatures/raja-ram-mohan-roy.jpg` | `https://indianliberals.in/wp-content/uploads/2022/11/RAJA-MOHAN.jpg` |

### Ring portraits
| Local | Source |
|---|---|
| `thinkers/ring-portraits/arun-shourie.webp` | `https://indianliberals.in/wp-content/uploads/2022/11/Arun-Shourie.webp` |
| `thinkers/ring-portraits/christopher-lingle.webp` | `https://indianliberals.in/wp-content/uploads/2022/11/Christopher-Lingle-2021.webp` |
| `thinkers/ring-portraits/tom-g-palmer.webp` | `https://indianliberals.in/wp-content/uploads/2022/11/Dr.-Tom-G.-Palmer.webp` |

### Photos
| Local | Source |
|---|---|
| `thinkers/photos/a-d-shroff.png` | `https://indianliberals.in/wp-content/uploads/2020/10/A-D-Shroff.png` |
| `thinkers/photos/b-r-shenoy.jpg` | `https://indianliberals.in/wp-content/uploads/2020/10/B-R-Shenoy.jpg` |
| `thinkers/photos/c-rajagopalachari.jpg` | `https://indianliberals.in/wp-content/uploads/2020/10/C-Rajagopalachari-profile.jpg` |
| `thinkers/photos/d-r-pendse.png` | `https://indianliberals.in/wp-content/uploads/2020/10/D-R-Pendse.png` |
| `thinkers/photos/m-r-pai.jpg` | `https://indianliberals.in/wp-content/uploads/2020/10/M-r-pai-profile.jpg` |
| `thinkers/photos/minoo-masani.jpg` | `https://indianliberals.in/wp-content/uploads/2020/10/Masani.jpg` |
| `thinkers/photos/s-v-raju.jpg` | `https://indianliberals.in/wp-content/uploads/2020/10/S-V-Raju-e1607799326174.jpg` |
| `thinkers/photos/s-v-raju-original.jpg` | `https://indianliberals.in/wp-content/uploads/2020/10/S-V-Raju.jpg` |
| `thinkers/photos/sauvik-chakraverti.jpg` | `https://indianliberals.in/wp-content/uploads/2020/10/Sauvik-Chakraverti.jpg` |
| `thinkers/photos/gopal-krishna-gokhale.jpeg` | `https://indianliberals.in/wp-content/uploads/2020/10/gopal_krishna_gokhale.jpeg` |
| `thinkers/photos/gopal-krishna-gokhale-alt.jpg` | `https://indianliberals.in/wp-content/uploads/2020/10/gopal-krishna-gokhale.jpg` |
| `thinkers/photos/nani-palkhivala.jpg` | `https://indianliberals.in/wp-content/uploads/2020/10/nani-palkhivala-profile.jpg` |
| `thinkers/photos/sharad-joshi.jpg` | `https://indianliberals.in/wp-content/uploads/2020/10/sharad-anantrao-joshi-profile.jpg` |
| `thinkers/photos/sudha-r-shenoy.jpg` | `https://indianliberals.in/wp-content/uploads/2020/10/sudha-r-shenoy.jpg` |
| `thinkers/photos/ramabai-pandita.jpg` | `https://indianliberals.in/wp-content/uploads/2021/06/ramabai-pandita-image.jpg` |
