# Builds docs/Sentinel-final-pitch.pptx (and .pdf) from the content of
# docs/PITCH_DECK.md by driving PowerPoint itself over COM -- no package
# downloads, and the render a judge sees is the render PowerPoint makes.
# Needs PowerPoint installed. Run from anywhere:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_pitch_deck.ps1
# Slide images for a visual check land in %TEMP%\sentinel-deck-png.
# When a number changes, change PITCH_DECK.md first, then this file, then rebuild.
$ErrorActionPreference = "Stop"
$REPO  = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$SHOTS = "$REPO\docs\img\pitch"
$OUT_PPTX = "$REPO\docs\Sentinel-final-pitch.pptx"
$OUT_PDF  = "$REPO\docs\Sentinel-final-pitch.pdf"
$PNG_DIR  = Join-Path $env:TEMP "sentinel-deck-png"

function RGB($r, $g, $b) { return [int]($r + $g * 256 + $b * 65536) }
$C = @{
  navy   = (RGB 26 32 48);    white = (RGB 255 255 255); ink    = (RGB 31 36 48)
  muted  = (RGB 107 114 128); amber = (RGB 217 164 65);  slate  = (RGB 59 74 107)
  panel  = (RGB 243 244 246); dpanel = (RGB 36 43 61);   warn   = (RGB 255 244 224)
  purple = (RGB 124 92 191);  line  = (RGB 209 213 219); dtext  = (RGB 226 229 236)
  amberdk = (RGB 156 108 24); green = (RGB 22 128 84)
}
$HEAD = "Cambria"; $BODY = "Calibri"; $MSO_TRUE = -1; $MSO_FALSE = 0
$W = 960; $H = 540; $M = 48

function New-Slide($pres, $bg) {
  $s = $pres.Slides.Add($pres.Slides.Count + 1, 12)
  $s.FollowMasterBackground = 0
  $s.Background.Fill.Solid()
  $s.Background.Fill.ForeColor.RGB = $bg
  return $s
}
function Add-Text($s, $t, $x, $y, $w, $h, $size, $color, $bold, $font, $align, $anchor) {
  $tb = $s.Shapes.AddTextbox(1, [double]$x, [double]$y, [double]$w, [double]$h)
  $tf = $tb.TextFrame
  $tf.WordWrap = -1; $tf.AutoSize = 0
  $tf.MarginLeft = 0; $tf.MarginRight = 0; $tf.MarginTop = 0; $tf.MarginBottom = 0
  $tf.VerticalAnchor = [int]$anchor
  $tr = $tf.TextRange
  $tr.Text = $t
  try { $tr.Font.Size = [double]$size } catch { throw ("Font.Size failed for text [" + $t + "] size=[" + $size + "] type=" + $size.GetType().FullName) }
  try { $tr.Font.Name = $font } catch { throw ("Font.Name failed for text [" + $t + "] font=[" + $font + "] type=" + $font.GetType().FullName) }
  try { $tr.Font.Bold = [int]$bold } catch { throw ("Font.Bold failed for text [" + $t + "] bold=[" + $bold + "] type=" + $bold.GetType().FullName) }
  $tr.Font.Color.RGB = [int]$color
  $tr.ParagraphFormat.Alignment = [int]$align
  return $tb
}
function Add-Body($s, $t, $x, $y, $w, $h, $size, $color) { return (Add-Text $s $t $x $y $w $h $size $color 0 $BODY 1 1) }
function Add-Bold($s, $t, $x, $y, $w, $h, $size, $color) { return (Add-Text $s $t $x $y $w $h $size $color $MSO_TRUE $BODY 1 1) }
function Add-Bullets($s, $items, $x, $y, $w, $h, $size, $color, $gap) {
  $tb = Add-Body $s ($items -join "`r") $x $y $w $h $size $color
  $pf = $tb.TextFrame.TextRange.ParagraphFormat
  $pf.Bullet.Visible = -1; $pf.Bullet.Character = 8226; $pf.Bullet.Font.Color.RGB = $C.amber
  $pf.LineRuleAfter = 0; $pf.SpaceAfter = [double]$gap
  $tb.TextFrame.Ruler.Levels(1).FirstMargin = 0; $tb.TextFrame.Ruler.Levels(1).LeftMargin = 14
  return $tb
}
function Add-Rect($s, $x, $y, $w, $h, $fill, $radius, $lineColor) {
  $shape = 1; if ($radius -gt 0) { $shape = 5 }
  $sh = $s.Shapes.AddShape([int]$shape, [double]$x, [double]$y, [double]$w, [double]$h)
  $sh.Fill.Solid(); $sh.Fill.ForeColor.RGB = [int]$fill
  if ($null -eq $lineColor) { $sh.Line.Visible = 0 } else { $sh.Line.ForeColor.RGB = $lineColor; $sh.Line.Weight = 0.75 }
  if ($radius -gt 0) { $sh.Adjustments.Item(1) = $radius }
  $sh.Shadow.Visible = 0
  return $sh
}
function Add-Circle($s, $x, $y, $d, $fill, $label, $labelColor) {
  $sh = $s.Shapes.AddShape(9, [double]$x, [double]$y, [double]$d, [double]$d)
  $sh.Fill.Solid(); $sh.Fill.ForeColor.RGB = [int]$fill; $sh.Line.Visible = 0; $sh.Shadow.Visible = 0
  if ($label) {
    $tr = $sh.TextFrame.TextRange; $tr.Text = $label; $tr.Font.Size = [double]($d * 0.45); $tr.Font.Bold = [int]-1
    $tr.Font.Name = $BODY; $tr.Font.Color.RGB = [int]$labelColor; $tr.ParagraphFormat.Alignment = 2
    $sh.TextFrame.MarginLeft = 0; $sh.TextFrame.MarginRight = 0; $sh.TextFrame.MarginTop = 0; $sh.TextFrame.MarginBottom = 0
    $sh.TextFrame.VerticalAnchor = 3
  }
  return $sh
}
function Add-Arrow($s, $x1, $y1, $x2, $y2, $color, $weight) {
  $ln = $s.Shapes.AddLine([double]$x1, [double]$y1, [double]$x2, [double]$y2)
  $ln.Line.ForeColor.RGB = [int]$color; $ln.Line.Weight = [double]$weight; $ln.Line.EndArrowheadStyle = 2
  return $ln
}
function Add-Pic($s, $path, $x, $y, $w, $maxH) {
  $img = [System.Drawing.Image]::FromFile($path)
  $ratio = [double]$img.Height / $img.Width
  $img.Dispose()
  $h = [double]$w * $ratio
  if ($maxH -and $h -gt $maxH) { $h = [double]$maxH; $w = $h / $ratio }
  $p = $s.Shapes.AddPicture($path, 0, -1, [double]$x, [double]$y, [double]$w, [double]$h)
  $p.Line.Visible = -1; $p.Line.ForeColor.RGB = $C.line; $p.Line.Weight = 0.75
  return $p
}
function Add-Title($s, $t, $dark) {
  $col = $C.ink; if ($dark) { $col = $C.white }
  return (Add-Text $s $t $M 36 ($W - 2 * $M) 50 32 $col $MSO_TRUE $HEAD 1 3)
}
function Add-Tag($s, $t, $dark) {
  $col = $C.muted; if ($dark) { $col = $C.dtext }
  return (Add-Text $s $t.ToUpper() $M ($H - 34) ($W - 2 * $M) 16 9 $col 0 $BODY 3 1)
}
function Set-Notes($s, $t) { $s.NotesPage.Shapes[2].TextFrame.TextRange.Text = $t }

Add-Type -AssemblyName System.Drawing
$app = New-Object -ComObject PowerPoint.Application
$pres = $app.Presentations.Add(0)
$pres.PageSetup.SlideSize = 15
$pres.PageSetup.SlideWidth = 960; $pres.PageSetup.SlideHeight = 540   # 13.333 x 7.5 in

# ---------------------------------------------------------------- 1 · title
$s = New-Slide $pres $C.navy
Add-Text $s "Sentinel" $M 150 600 80 60 $C.amber $MSO_TRUE $HEAD 1 1 | Out-Null
Add-Text $s "Every answer comes with its evidence." $M 230 700 44 28 $C.white 0 $HEAD 1 1 | Out-Null
Add-Text $s "A document checker that is confidently wrong is worse than no checker at all - because nobody goes back and looks." $M 290 620 60 16 $C.dtext 0 $BODY 1 1 | Out-Null
$tb = Add-Text $s "DuoCode  ·  Tang Chye Fong  ·  Lim Yee Teng  ·  Asia Pacific University" $M ($H - 96) 640 22 13 $C.dtext 0 $BODY 1 1
Add-Text $s "duocode-sentinel.vercel.app  ·  github.com/TCF1209/duocode-sentinel" $M ($H - 70) 640 22 12 $C.amber 0 $BODY 1 1 | Out-Null
Add-Text $s "Averis x Monash Hackathon 2026 · Final Round" ($W - $M - 320) ($H - 70) 320 22 12 $C.dtext 0 $BODY 3 1 | Out-Null
Set-Notes $s "We're DuoCode. Sentinel is built on one rule: it never reports anything it cannot prove. Everything in the next five minutes is evidence for that sentence. (0:00-0:15)"

# -------------------------------------------------------------- 2 · problem
$s = New-Slide $pres $C.white
Add-Title $s "The problem - and the fourth case" $false | Out-Null
$caps = @(
  @("Classify", "Tell message types apart: comparison requests, new SI requests, invoice queries, general mail, spam."),
  @("Extract", "For comparison requests, read the SI and BL attachments and pull the matching shipment fields."),
  @("Compare", "Surface any mismatched fields, showing the SI and BL values side by side."),
  @("Ask for help", "When it can't finish on its own, escalate to a person with full context instead of guessing or failing silently.")
)
$bw = 204; $gapx = 16; $x = $M; $y = 104
for ($i = 0; $i -lt 4; $i++) {
  Add-Rect $s $x $y $bw 150 $C.panel 0.08 $null | Out-Null
  Add-Circle $s ($x + 14) ($y + 14) 30 $C.amber ("0" + ($i + 1)) $C.ink | Out-Null
  Add-Bold $s $caps[$i][0] ($x + 52) ($y + 18) ($bw - 64) 24 16 $C.ink | Out-Null
  Add-Body $s $caps[$i][1] ($x + 14) ($y + 54) ($bw - 28) 90 12 $C.ink | Out-Null
  $x += $bw + $gapx
}
Add-Text $s "Why we built it: today a documentation clerk does this by hand - about 4 minutes per SI/BL pair and 20 seconds to triage each email (a conservative estimate, not a measurement) - and a missed field becomes a correction, a delay, rework." $M 266 ($W - 2 * $M) 34 11.5 $C.ink 0 $BODY 1 1 | Out-Null
$pains = @(
  @("Finding the right emails takes time", "A document request that is overlooked never reaches the checking step."),
  @("Manual comparison is easy to get wrong", "Names, ports, quantities and weight across two documents; a missed discrepancy is a correction, a delay, rework."),
  @("The same fact looks different", "One document says 'Port of Loading', the other 'Load Port' - the system has to know they are the same field.")
)
$cw = 277; $x = $M; $y = 306
for ($i = 0; $i -lt 3; $i++) {
  Add-Bold $s $pains[$i][0] $x $y $cw 40 14 $C.slate | Out-Null
  Add-Body $s $pains[$i][1] $x ($y + 42) $cw 70 12 $C.ink | Out-Null
  $x += $cw + 16
}
Add-Rect $s $M 436 ($W - 2 * $M) 44 $C.warn 0.15 $null | Out-Null
Add-Text $s "The fourth case: sometimes the check cannot be done at all - an unreadable scan, a blank field, the wrong document. That has to reach a person with the reason attached, not be guessed at. Sentinel does all four." ($M + 16) 443 ($W - 2 * $M - 32) 32 12 $C.ink 0 $BODY 1 3 | Out-Null
Add-Tag $s "Criterion 5 · Solution effectiveness & user value" $false | Out-Null
Set-Notes $s "Why we built it: a shipping desk gets five kinds of mail in one inbox, and for every document check a person compares the Shipping Instruction against the draft Bill of Lading - seven fields, by hand. At a conservative estimate that is about four minutes a pair and twenty seconds to triage each email; this inbox alone is a day and a half of desk work. Miss one field and it's a correction, a delay, rework. And there's a fourth case the statement names: sometimes the check can't be done - an unreadable scan, a blank field, the wrong document. That has to reach a person with the reason, not be guessed at. Sentinel does all four. (0:15-0:40)"

# ------------------------------------------------------ 3 · what it does
$s = New-Slide $pres $C.white
Add-Title $s "What it does, end to end" $false | Out-Null
Add-Pic $s "$SHOTS\run_page.png" $M 100 540 | Out-Null
$stats = @(@("520", "emails, classified and routed"), @("46", "mismatches, with the fields that differ"), @("20", "sent to a person - with the reason and what to do"), @("12.7 s", "for the whole inbox, on a free-tier container"))
$x = 620; $y = 100
foreach ($st in $stats) {
  Add-Text $s $st[0] $x $y 300 46 40 $C.amber $MSO_TRUE $HEAD 1 1 | Out-Null
  Add-Body $s $st[1] $x ($y + 46) 292 30 12 $C.ink | Out-Null
  $y += 92
}
Add-Text $s "How a desk uses it:   1  Run the inbox   ·   2  Open a flagged case   ·   3  Confirm it, correct a single field, or re-upload the corrected document   ·   4  Send the drafted reply" $M 450 ($W - 2 * $M) 30 11.5 $C.ink 0 $BODY 1 1 | Out-Null
Add-Tag $s "Criterion 1 · End-to-end functionality" $false | Out-Null
Set-Notes $s "This is the whole inbox, live on Render and Vercel - not a sample, the organisers' 520 emails. Every email classified, every document pair compared, every case Sentinel can't decide sent to a person with the reason attached. Thirteen seconds. And this is how a desk uses it, four steps: run the inbox, open a flagged case, confirm it or correct one field or re-upload the corrected document, send the drafted reply. Do not say the accuracy here - that is slide 6. (0:40-1:05)"

# ------------------------------------------------------ 4 · how it decides
$s = New-Slide $pres $C.white
Add-Title $s "How it decides" $false | Out-Null
$stages = @("Classify", "Intake", "Extract", "Compare", "GATE", "Decide")
$sw = 122; $sh = 54; $sg = 22; $x = $M + 8; $y = 118
for ($i = 0; $i -lt 6; $i++) {
  $fill = $C.panel; $col = $C.ink; if ($i -eq 4) { $fill = $C.amber }
  $r = Add-Rect $s $x $y $sw $sh $fill 0.18 $null
  $tr = $r.TextFrame.TextRange; $tr.Text = $stages[$i]; $tr.Font.Name = $HEAD; $tr.Font.Size = 15; $tr.Font.Bold = -1
  $tr.Font.Color.RGB = $col; $tr.ParagraphFormat.Alignment = 2; $r.TextFrame.VerticalAnchor = 3
  if ($i -lt 5) { Add-Arrow $s ($x + $sw + 3) ($y + $sh / 2) ($x + $sw + $sg - 3) ($y + $sh / 2) $C.slate 1.5 | Out-Null }
  $x += $sw + $sg
}
# the veto: from the gate back over the comparison
$gx = $M + 8 + 4 * ($sw + $sg); $cx = $M + 8 + 3 * ($sw + $sg)
$veto = $s.Shapes.AddLine(($gx + $sw / 2), $y - 6, ($cx + $sw / 2), $y - 6)
$veto.Line.ForeColor.RGB = $C.amberdk; $veto.Line.Weight = 1.5; $veto.Line.EndArrowheadStyle = 2; $veto.Line.DashStyle = 4
Add-Text $s "can veto the comparison" ($cx + 10) ($y - 30) 260 18 10 $C.amberdk 0 $BODY 2 1 | Out-Null
Add-Text $s "Six stages, one direction. The gate runs after the comparison: a value we cannot find again in the document it was read from is never reported as a discrepancy - it becomes a question for a person, with both readings attached." $M 190 ($W - 2 * $M) 36 12 $C.ink 0 $BODY 1 1 | Out-Null
$dec = @(
  @("Labels by meaning, values exactly", "Never a similarity score. A threshold loose enough to forgive a scan artefact also merges two real companies - and this data has them."),
  @("Rules first, model second", "Every stage tries a deterministic answer before a model, and records which one answered (decided_by). The model is asked only where the rules admit they cannot read."),
  @("One stateless pipeline library", "No web framework or database in backend/sdoc. The CLI, the API and the tests run the same code, so the thing scored is the thing demonstrated.")
)
$cw = 277; $x = $M; $y = 244
for ($i = 0; $i -lt 3; $i++) {
  Add-Rect $s $x $y $cw 160 $C.panel 0.08 $null | Out-Null
  Add-Bold $s $dec[$i][0] ($x + 14) ($y + 14) ($cw - 28) 40 14 $C.slate | Out-Null
  Add-Body $s $dec[$i][1] ($x + 14) ($y + 56) ($cw - 28) 100 11.5 $C.ink | Out-Null
  $x += $cw + 16
}
Add-Text $s "Scaling, as built: state sits behind one class in one file (store.py) - Postgres is a one-file change · one worker on purpose · throughput is more copies of a stateless library · cost does not scale with volume on this inbox · per-desk rules slot into the existing stage boundaries." $M 418 ($W - 2 * $M) 40 11 $C.muted 0 $BODY 1 1 | Out-Null
Add-Tag $s "Criterion 2 · Architecture & scalability" $false | Out-Null
Set-Notes $s "Six stages, one direction. Two choices carry the design. Values are compared exactly after canonicalising, never by similarity - a threshold loose enough to forgive a scan artefact also merges two real companies, and the data has those. And the gate after the comparison can overrule it: a value we cannot find again in the document it was read from is never reported as a discrepancy - it becomes a question for a person. The pipeline is a stateless library with no web or database in it, which is also the scaling story: throughput is more copies of it; the state sits behind one class in one file. (1:05-1:40)"

# ------------------------------------------------------ 5 · where the AI is
$s = New-Slide $pres $C.white
Add-Title $s "Where the AI is - and why it is aimed" $false | Out-Null
$rows = @(
  @("C", "Classify", "an email the rules cannot separate", "asked only when the rule score is ambiguous; a closed five-way answer, never free text"),
  @("R", "Read", "a field label the table has never seen", "asked only about fields no rule resolved; every value must be found again in the document before it is adopted"),
  @("S", "See", "a scanned page with no text layer", "transcribed for the reviewer, never fed into a comparison - the case stays in review")
)
$y = 104
foreach ($r in $rows) {
  Add-Circle $s $M $y 34 $C.purple $r[0] $C.white | Out-Null
  Add-Bold $s ($r[1] + " - " + $r[2]) ($M + 48) ($y - 2) 470 22 14 $C.ink | Out-Null
  Add-Body $s $r[3] ($M + 48) ($y + 22) 470 44 11.5 $C.muted | Out-Null
  $y += 82
}
Add-Text $s "gpt-5-mini, structured output. One rule for all three: nothing the model returns is adopted until it is found again in the document." $M 352 520 40 12 $C.ink 0 $BODY 1 1 | Out-Null
Add-Rect $s 600 104 312 226 $C.panel 0.08 $null | Out-Null
Add-Text $s "168" 612 122 130 70 56 $C.muted $MSO_TRUE $HEAD 3 1 | Out-Null
Add-Text $s "→" 748 130 30 50 30 $C.muted 0 $BODY 2 1 | Out-Null
Add-Text $s "2" 786 122 110 70 56 $C.amber $MSO_TRUE $HEAD 1 1 | Out-Null
Add-Body $s "cases forced to a human on wording we invented - rules alone vs rules + model, 188 documents" 616 200 280 40 11.5 $C.ink | Out-Null
Add-Bold $s "False discrepancies: 0 both ways. Recall bought by guessing would have shown up there; it didn't." 616 250 280 60 11.5 $C.slate | Out-Null
Add-Rect $s $M 404 ($W - 2 * $M) 54 $C.warn 0.15 $null | Out-Null
Add-Text $s "`$0.0013 per document at the published rates · cached · `$2 ceiling per run.   On this inbox: 0 classifier calls, 0 extractor calls, 6 scans read out for the reviewer - every decision is a rule's, and that is measured, not assumed." ($M + 16) 410 ($W - 2 * $M - 32) 42 11.5 $C.ink 0 $BODY 1 3 | Out-Null
Add-Tag $s "Criterion 3 · Technology integration" $false | Out-Null
Set-Notes $s "Never say 'we use less AI'. Say: the AI is reserved for the cases the rules cannot handle - and the system performs just as well. A judge in the first round said we use AI less than most teams. True, and measured. On this inbox the rules answer all 520 and the scoring is all-or-nothing per email, so a model that is almost always right costs places. The model goes only where the rules admit they can't read: an ambiguous email, a label we've never seen, a scanned page. On documents with wording we invented, rules alone send 168 of 188 cases to a human; with the model, two - and false discrepancies stay at zero, because nothing the model says is adopted until we find it again in the source. You'll see both in the demo: a scan read out for the reviewer, and four unknown labels read on request. (1:40-2:20)"

# ------------------------------------------------------ 6 · how we know
$s = New-Slide $pres $C.white
Add-Title $s "How we know it holds" $false | Out-Null
$cards = @(
  @("Not memorised", "1.0000 on four datasets, three from seeds we never developed against - 225 planted defects caught with the exact field set, 80/80 escalations correct."),
  @("Attacked ourselves", "16 kinds of damage, 3,008 perturbed documents, 20,496 field reads, no answer key. Thirteen modes at zero movement; silent wrong values 982 -> 0."),
  @("A real carrier's form", "CMA CGM's public SI template, from outside the generator: four fields held, one bug found and fixed the same day."),
  @("Engineering", "756 tests, 0 failing; CI on every push; a container that runs as a non-root user with no secret baked in; every value carries its evidence.")
)
$cw = 272; $ch = 150; $x = $M; $y = 100
for ($i = 0; $i -lt 4; $i++) {
  $cx = $M + ($i % 2) * ($cw + 14); $cy = 100 + [math]::Floor($i / 2) * ($ch + 14)
  Add-Rect $s $cx $cy $cw $ch $C.panel 0.08 $null | Out-Null
  Add-Bold $s $cards[$i][0] ($cx + 14) ($cy + 12) ($cw - 28) 24 15 $C.slate | Out-Null
  Add-Body $s $cards[$i][1] ($cx + 14) ($cy + 40) ($cw - 28) 104 11.5 $C.ink | Out-Null
}
$hx = $M + 2 * ($cw + 14) + 4; $hw = $W - $M - $hx
Add-Rect $s $hx 100 $hw 314 $C.warn 0.08 $null | Out-Null
Add-Bold $s "What we haven't fixed" ($hx + 14) 112 ($hw - 28) 24 15 $C.amberdk | Out-Null
Add-Body $s "email_145: a wrapped party name cut short to exactly what the other document says leaves the repair nothing to repair, and one real mismatch in 3,008 perturbed documents is reported as a match.`r`rThe obvious guard would flag 114 of 124 SI/BL pairs (92%) - worse than the gap - so it stays open and written down (ADVERSARIAL.md 5.2)." ($hx + 14) 142 ($hw - 28) 200 11.5 $C.ink | Out-Null
Add-Bold $s "A defect we hide is worse than one we miss." ($hx + 14) 352 ($hw - 28) 50 12 $C.amberdk | Out-Null
Add-Text $s "A perfect score on the dataset you were handed proves you didn't memorise it. It doesn't prove the reader works - so we went looking for the failures ourselves." $M 432 ($W - 2 * $M) 30 11.5 $C.muted 0 $BODY 1 1 | Out-Null
Add-Tag $s "Criterion 4 · Engineering quality & robustness" $false | Out-Null
Set-Notes $s "A perfect score on the dataset you were handed proves you didn't memorise it. It doesn't prove the reader works. So we attacked our own reader - three thousand perturbed documents, sixteen kinds of damage, no answer key. Thirteen of sixteen don't move. OCR noise used to produce 982 silently wrong values; it produces zero now, because a damaged number is refused instead of parsed short. Then we fed it a real carrier's template from outside the generator, and it found a bug we fixed the same day. And the one we haven't fixed is on the slide, because a defect we hide is worse than one we miss. (2:20-2:55)"

# ------------------------------------------------------ 7 · live demo divider
$s = New-Slide $pres $C.navy
Add-Title $s "Live demo" $true | Out-Null
Add-Text $s "90 seconds, on the deployed URLs" $M 84 500 24 14 $C.amber 0 $BODY 1 1 | Out-Null
$steps = @(
  "Start a run with the model tier on - then Before / With Sentinel: the inbox as it arrived, and what it made of it",
  "Patterns worth a second look - one shipper, one field, seven times",
  "A mismatch case - under every value, the line it was read from",
  "A scanned case - the page read out for the reviewer; the case still in review, decided per field",
  "Compare, unfamiliar labels: model off, then on - 'model answered'"
)
$y = 124
for ($i = 0; $i -lt 5; $i++) {
  Add-Circle $s $M $y 28 $C.amber ([string]($i + 1)) $C.ink | Out-Null
  Add-Text $s $steps[$i] ($M + 40) ($y + 2) 400 48 13 $C.white 0 $BODY 1 1 | Out-Null
  $y += 62
}
Add-Pic $s "$SHOTS\scan_case.png" 520 110 392 | Out-Null
Add-Text $s "Fallback if the venue network fails: the same inbox on the laptop, 1.5 s, no network - only the model beat changes." $M 448 460 40 11 $C.dtext 0 $BODY 1 1 | Out-Null
Set-Notes $s "At the mismatch case: 'Under every value - the line it was read from. A reviewer never has to open the source document to trust this.' At the scan: 'No text layer, so Sentinel did not decide. But the model read the page for the reviewer - seven fields, and it says which ones it couldn't read rather than guessing. The case stays in review; the person decides, per field.' At Compare, off: 'wording our table has never seen - the honest answer is can't read it, and it says which labels.' On: 'the model reads them, every value re-located in the document before it's adopted, and it surfaces the real discrepancy - badge says model answered.' (2:55-4:25)"

# ------------------------------------------------------ 8 · reviewer UX
$s = New-Slide $pres $C.white
Add-Title $s "What makes it different" $false | Out-Null
$feat = @(
  @("Correct by re-upload", "The sender re-sends a fixed SI or BL? Attach it on the case and the same check runs again. The old answer stays on record."),
  @("Scans read out for the reviewer", "An image-only PDF still goes to a person - but with the seven fields already read by the model, marked as evidence, not a verdict."),
  @("Shipper history on the field", "Correcting a field shows how often this shipper was wrong on that same field before. A count, not a guess."),
  @("The original, one click away", "Every value carries its line, and the source document opens beside it."),
  @("A reply drafted from the corrected outcome", "Subject and body ready, built from what the reviewer decided - not the stale answer. A person still presses send.")
)
$y = 96
for ($i = 0; $i -lt 5; $i++) {
  Add-Circle $s $M $y 26 $C.amber ([string]($i + 1)) $C.ink | Out-Null
  Add-Bold $s $feat[$i][0] ($M + 36) ($y - 2) 440 22 13.5 $C.ink | Out-Null
  Add-Body $s $feat[$i][1] ($M + 36) ($y + 20) 440 44 11 $C.muted | Out-Null
  $y += 68
}
Add-Pic $s "$SHOTS\scan_case_crop.png" 540 96 372 236 | Out-Null
Add-Body $s "The scan read-out, as the reviewer sees it: seven fields, the model's confidence, and the sentence that none of it entered the comparison." 540 340 372 44 10.5 $C.muted | Out-Null
Add-Rect $s $M 440 ($W - 2 * $M) 40 $C.warn 0.15 $null | Out-Null
Add-Text $s "Every flag carries the line it came from. Every escalation carries the reason and what to do about it. Most teams at this stage meet the brief; these are the things a reviewer actually uses." ($M + 16) 446 ($W - 2 * $M - 32) 28 11.5 $C.ink 0 $BODY 1 3 | Out-Null
Add-Tag $s "Criterion 6 · User experience & differentiation" $false | Out-Null
Set-Notes $s "At the top-ten stage everyone meets the brief, so this is the slide to slow down on - thirty seconds. Five things the others mostly don't have: the sender re-sends a fixed document and you re-upload it on the case, the check runs again and the old answer stays on record; a scan still goes to a person but already read out by the model; correcting a field shows this shipper's history on that field; the original document is one click away from every value; and the reply is drafted from what the reviewer decided, not the stale answer. (4:10-4:40)"

# ------------------------------------------------------ 9 · impact & next
$s = New-Slide $pres $C.white
Add-Title $s "Impact, and what comes next" $false | Out-Null
Add-Rect $s $M 96 500 96 $C.panel 0.08 $null | Out-Null
Add-Text $s "11 hours" ($M + 16) 108 190 60 36 $C.muted $MSO_TRUE $HEAD 1 3 | Out-Null
Add-Text $s "→" ($M + 210) 116 40 44 24 $C.muted 0 $BODY 2 3 | Out-Null
Add-Text $s "13 seconds" ($M + 254) 104 236 66 40 $C.amber $MSO_TRUE $HEAD 1 3 | Out-Null
Add-Body $s "520 emails, 124 document pairs. Eleven hours is a conservative estimate (20 s an email, 4 min a pair), not a measurement; thirteen seconds is measured. Every decision on that inbox was a rule's." ($M + 16) 158 470 32 10.5 $C.muted | Out-Null
Add-Bold $s "First deployment: one desk, not a region" $M 208 500 22 14 $C.slate | Out-Null
Add-Body $s "The inbox already carries four desk codes (AFEMY 35, AIE 30, AFRT 29, AFPTME 22 emails). Sentinel sits beside the desk's existing check until the measures below have held for a full cycle of its carriers." $M 232 500 48 11.5 $C.ink | Out-Null
$tblShape = $s.Shapes.AddTable(4, 3, $M, 290, 500, 150)
$tbl = $tblShape.Table
$tbl.ApplyStyle("{5940675A-B579-460E-94D1-54222C63F5DA}", 0)
$cells = @(
  @("Measure", "Today (graded inbox)", "The pilot watches"),
  @("Escalation rate", "20 of 220 requests (9.1%), all correct", "precision at 1.0 as unfamiliar templates grow"),
  @("False alarms", "0 of 46 defects; 0 across 16 perturbation modes", "the weekly number"),
  @("Reviewer minutes per escalation", "not measured yet", "the pilot's first new measurement")
)
for ($ri = 1; $ri -le 4; $ri++) { for ($ci = 1; $ci -le 3; $ci++) {
  $tr = $tbl.Cell($ri, $ci).Shape.TextFrame.TextRange
  $tr.Text = $cells[$ri - 1][$ci - 1]; $tr.Font.Size = [double]10.5; $tr.Font.Name = $BODY; $tr.Font.Color.RGB = [int]$C.ink
  $cellShape = $tbl.Cell($ri, $ci).Shape
  if ($ri -eq 1) { $tr.Font.Bold = [int]-1; $tr.Font.Color.RGB = [int]$C.white; $cellShape.Fill.Solid(); $cellShape.Fill.ForeColor.RGB = [int]$C.slate } else { $cellShape.Fill.Solid(); $cellShape.Fill.ForeColor.RGB = [int]$C.white }
} }
$tbl.Columns.Item(1).Width = 150; $tbl.Columns.Item(2).Width = 190; $tbl.Columns.Item(3).Width = 160
Add-Rect $s 580 96 332 344 $C.panel 0.08 $null | Out-Null
Add-Bold $s "Next, in order" 596 110 300 24 15 $C.slate | Out-Null
$next = @(
  @("1", "Per-desk rules", "a label table and an escalation policy per desk, selected by the code the inbox already carries"),
  @("2", "Corrections feed the label table", "every confirmed correction is a labelled example of wording we could not read - the one place this system should learn"),
  @("3", "The database", "one file; the demo does not need it yet, a pilot will")
)
$y = 146
foreach ($n in $next) {
  Add-Circle $s 596 $y 26 $C.amber $n[0] $C.ink | Out-Null
  Add-Bold $s $n[1] 632 ($y - 1) 268 22 13 $C.ink | Out-Null
  Add-Body $s $n[2] 632 ($y + 20) 268 62 11 $C.muted | Out-Null
  $y += 92
}
Add-Text $s "Cheap because the model is aimed, not because it is absent." $M 452 500 22 12 $C.amberdk $MSO_TRUE $BODY 1 1 | Out-Null
Add-Tag $s "Criterion 7 · Impact & future potential" $false | Out-Null
Set-Notes $s "520 emails and 124 document pairs is, at a conservative estimate, about eleven hours of desk work. Sentinel does it in thirteen seconds and every decision on that inbox was a rule, so it costs nothing to run - cheap because the model is aimed, not because it's absent. The first deployment is one desk, with three numbers we'd watch; two of them we can already show you and the third is what the pilot is for. Say 'at a conservative estimate' aloud, always. (4:40-4:58)"

# ------------------------------------------------------ 10 · close
$s = New-Slide $pres $C.navy
Add-Text $s "Every answer comes with its evidence." $M 200 ($W - 2 * $M) 60 36 $C.white $MSO_TRUE $HEAD 2 3 | Out-Null
Add-Text $s "Sentinel, by DuoCode" $M 268 ($W - 2 * $M) 30 18 $C.amber 0 $HEAD 2 1 | Out-Null
Add-Text $s "github.com/TCF1209/duocode-sentinel  ·  duocode-sentinel.vercel.app" $M 310 ($W - 2 * $M) 24 13 $C.dtext 0 $BODY 2 1 | Out-Null
Set-Notes $s "Sentinel, by DuoCode. Every answer comes with its evidence. Thank you. (4:58-5:00)"

# ------------------------------------------------------ save + render
if (Test-Path $OUT_PPTX) { Remove-Item $OUT_PPTX -Force }
if (Test-Path $OUT_PDF)  { Remove-Item $OUT_PDF -Force }
if (Test-Path $PNG_DIR)  { Remove-Item $PNG_DIR -Recurse -Force }
$pres.SaveAs($OUT_PPTX)
$pres.Export($PNG_DIR, "PNG", 1920, 1080)
$pres.SaveAs($OUT_PDF, 32)
$pres.Close(); $app.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
Write-Output ("slides: " + (Get-ChildItem $PNG_DIR | Measure-Object).Count)
Get-Item $OUT_PPTX, $OUT_PDF | Select-Object Name, Length | Format-Table -AutoSize
