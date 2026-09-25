# Builds docs/Sentinel-final-pitch.pptx (and .pdf) from the content of
# docs/PITCH_DECK.md by driving PowerPoint itself over COM -- no package
# downloads, and the render a judge sees is the render PowerPoint makes.
# Needs PowerPoint installed, and the .pptx closed. Run from anywhere:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_pitch_deck.ps1
# Slide images for a visual check land in %TEMP%\sentinel-deck-png.
# When a number changes, change PITCH_DECK.md first, then this file, then rebuild.
#
# 10-minute pitch, live demo inside it (25 Sep). Seven presented slides, then
# nine "demo backup" slides that are hidden in the slide show (skipped on
# stage) but included in the PDF, so a judge reading the submission sees
# every demo beat. Colours and serif headings follow the dashboard
# (web/app/globals.css) so the switch between deck and browser is seamless.
$ErrorActionPreference = "Stop"
$REPO  = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$SHOTS = "$REPO\docs\img\pitch"
$OUT_PPTX = "$REPO\docs\Sentinel-final-pitch.pptx"
$OUT_PDF  = "$REPO\docs\Sentinel-final-pitch.pdf"
$PNG_DIR  = Join-Path $env:TEMP "sentinel-deck-png"

function RGB($r, $g, $b) { return [int]($r + $g * 256 + $b * 65536) }
# The dashboard's own tokens (globals.css, light theme; dark slides use the dark theme's).
$C = @{
  bg     = (RGB 250 247 239); ink    = (RGB 24 35 53);    brown  = (RGB 143 90 32)
  muted  = (RGB 241 236 223); mfg    = (RGB 91 101 119);  line   = (RGB 227 218 195)
  card   = (RGB 255 255 255); ok     = (RGB 30 122 76);   okbg   = (RGB 225 239 227)
  warn   = (RGB 169 99 27);   warnbg = (RGB 245 231 206); danger = (RGB 172 51 39)
  dbg    = (RGB 18 24 31);    dfg    = (RGB 237 231 214); dcard  = (RGB 27 34 44)
  dgold  = (RGB 224 172 94);  dmfg   = (RGB 168 179 194); ai     = (RGB 107 79 160)
  aibg   = (RGB 238 233 246); white  = (RGB 255 255 255)
}
$HEAD = "Georgia"; $BODY = "Calibri"; $MSO_TRUE = -1
$W = 960; $H = 540; $M = 48

function New-Slide($pres, $bg) {
  $s = $pres.Slides.Add($pres.Slides.Count + 1, 12)
  $s.FollowMasterBackground = 0
  $s.Background.Fill.Solid()
  $s.Background.Fill.ForeColor.RGB = [int]$bg
  return $s
}
function Add-Text($s, $txt, $x, $y, $w, $h, $size, $color, $bold, $font, $align, $anchor) {
  $tb = $s.Shapes.AddTextbox(1, [double]$x, [double]$y, [double]$w, [double]$h)
  $tf = $tb.TextFrame
  $tf.WordWrap = -1; $tf.AutoSize = 0
  $tf.MarginLeft = 0; $tf.MarginRight = 0; $tf.MarginTop = 0; $tf.MarginBottom = 0
  $tf.VerticalAnchor = [int]$anchor
  $tr = $tf.TextRange
  $tr.Text = $txt
  $tr.Font.Size = [double]$size
  $tr.Font.Name = [string]$font
  $tr.Font.Bold = [int]$bold
  $tr.Font.Color.RGB = [int]$color
  $tr.ParagraphFormat.Alignment = [int]$align
  return $tb
}
function Add-Body($s, $txt, $x, $y, $w, $h, $size, $color) { return (Add-Text $s $txt $x $y $w $h $size $color 0 $BODY 1 1) }
function Add-Bold($s, $txt, $x, $y, $w, $h, $size, $color) { return (Add-Text $s $txt $x $y $w $h $size $color $MSO_TRUE $BODY 1 1) }
function Add-Rect($s, $x, $y, $w, $h, $fill, $radius, $lineColor) {
  $shape = 1; if ($radius -gt 0) { $shape = 5 }
  $sh = $s.Shapes.AddShape([int]$shape, [double]$x, [double]$y, [double]$w, [double]$h)
  $sh.Fill.Solid(); $sh.Fill.ForeColor.RGB = [int]$fill
  if ($null -eq $lineColor) { $sh.Line.Visible = 0 } else { $sh.Line.ForeColor.RGB = [int]$lineColor; $sh.Line.Weight = [double]0.75 }
  if ($radius -gt 0) { $sh.Adjustments.Item(1) = [double]$radius }
  $sh.Shadow.Visible = 0
  return $sh
}
function Add-Circle($s, $x, $y, $d, $fill, $label, $labelColor) {
  $sh = $s.Shapes.AddShape(9, [double]$x, [double]$y, [double]$d, [double]$d)
  $sh.Fill.Solid(); $sh.Fill.ForeColor.RGB = [int]$fill; $sh.Line.Visible = 0; $sh.Shadow.Visible = 0
  $tr = $sh.TextFrame.TextRange; $tr.Text = [string]$label; $tr.Font.Size = [double]($d * 0.45); $tr.Font.Bold = [int]-1
  $tr.Font.Name = $BODY; $tr.Font.Color.RGB = [int]$labelColor; $tr.ParagraphFormat.Alignment = 2
  $sh.TextFrame.MarginLeft = 0; $sh.TextFrame.MarginRight = 0; $sh.TextFrame.MarginTop = 0; $sh.TextFrame.MarginBottom = 0
  $sh.TextFrame.VerticalAnchor = 3
  return $sh
}
function Add-Arrow($s, $x1, $y1, $x2, $y2, $color, $weight) {
  $ln = $s.Shapes.AddLine([double]$x1, [double]$y1, [double]$x2, [double]$y2)
  $ln.Line.ForeColor.RGB = [int]$color; $ln.Line.Weight = [double]$weight; $ln.Line.EndArrowheadStyle = 2
  return $ln
}
function Add-Pic($s, $path, $x, $y, $w, $maxH) {
  if (-not (Test-Path $path)) { throw "missing capture: $path" }
  $img = [System.Drawing.Image]::FromFile($path)
  $ratio = [double]$img.Height / $img.Width
  $img.Dispose()
  $pw = [double]$w; $ph = $pw * $ratio
  if ($maxH -and $ph -gt $maxH) { $ph = [double]$maxH; $pw = $ph / $ratio }
  $p = $s.Shapes.AddPicture($path, 0, -1, [double]$x, [double]$y, [double]$pw, [double]$ph)
  $p.Line.Visible = -1; $p.Line.ForeColor.RGB = [int]$C.line; $p.Line.Weight = [double]0.75
  return $p
}
function Add-Title($s, $txt, $dark) {
  $col = $C.ink; if ($dark) { $col = $C.dfg }
  return (Add-Text $s $txt $M 30 ($W - 2 * $M) 46 30 $col $MSO_TRUE $HEAD 1 3)
}
function Add-Kicker($s, $txt, $dark) {
  $col = $C.brown; if ($dark) { $col = $C.dgold }
  return (Add-Text $s $txt.ToUpper() $M 16 ($W - 2 * $M) 14 9.5 $col $MSO_TRUE $BODY 1 1)
}
# The rubric criterion this slide is evidence for, bottom left, so a judge
# filling the score sheet can file it; the speaker never says it aloud.
function Add-Tag($s, $txt, $dark) {
  $col = $C.mfg; if ($dark) { $col = $C.dmfg }
  $t = Add-Text $s $txt.ToUpper() $M ($H - 28) ($W - 2 * $M) 14 9 $col $MSO_TRUE $BODY 1 1
  return $t
}
function Set-Notes($s, $txt) { $s.NotesPage.Shapes[2].TextFrame.TextRange.Text = $txt }
function Hide-Slide($s) { $s.SlideShowTransition.Hidden = -1 }

Add-Type -AssemblyName System.Drawing
$app = New-Object -ComObject PowerPoint.Application
$pres = $app.Presentations.Add(0)
$pres.PageSetup.SlideSize = 15
$pres.PageSetup.SlideWidth = 960; $pres.PageSetup.SlideHeight = 540   # 13.333 x 7.5 in

# ============================================================ 1 · title (A)
$s = New-Slide $pres $C.bg
Add-Kicker $s "Averis x Monash Hackathon 2026 · Final round" $false | Out-Null
Add-Text $s "Sentinel" $M 118 440 76 58 $C.ink $MSO_TRUE $HEAD 1 1 | Out-Null
Add-Text $s "Every answer comes with its evidence." $M 196 430 72 25 $C.brown 0 $HEAD 1 1 | Out-Null
Add-Body $s "A document checker that is confidently wrong is worse than none: nobody goes back to look. Sentinel never reports a discrepancy it cannot prove." $M 282 420 64 14.5 $C.mfg | Out-Null
Add-Rect $s $M 372 60 3 $C.brown 0 $null | Out-Null
Add-Bold $s "DuoCode" $M 388 420 20 14 $C.ink | Out-Null
Add-Body $s "Lim Yee Teng  ·  Tang Chye Fong  ·  Asia Pacific University" $M 408 430 20 13 $C.ink | Out-Null
Add-Body $s "duocode-sentinel.vercel.app`rgithub.com/TCF1209/duocode-sentinel" $M 440 430 40 12.5 $C.brown | Out-Null
Add-Pic $s "$SHOTS\run_page.png" 510 96 402 400 | Out-Null
Add-Body $s "The organisers' 520-email inbox, run live on the deployed site." 510 356 402 18 10.5 $C.mfg | Out-Null
Set-Notes $s "SPEAKER A (Yee Teng) · 0:00-0:15`r`rGood morning. We're DuoCode - I'm Yee Teng, this is Chye Fong. A checker that is confidently wrong is worse than none: nobody goes back to look. So Sentinel has one rule - it never reports a discrepancy it cannot prove."

# ============================================================ 2 · why we built it (A)
$s = New-Slide $pres $C.bg
Add-Kicker $s "Why we built it" $false | Out-Null
Add-Title $s "Four things the desk needs - the fourth matters most" $false | Out-Null
$caps = @(
  @("01", "Classify", "Tell message types apart: comparison requests, new SI requests, invoice queries, general mail, spam."),
  @("02", "Extract", "For comparison requests, read the SI and BL attachments and pull the matching shipment fields."),
  @("03", "Compare", "Surface any mismatched fields, showing the SI and BL values side by side."),
  @("04", "Ask for help", "When it can't finish on its own, escalate to a person with full context instead of guessing or failing silently.")
)
$bw = 204; $gapx = 16; $x = $M; $y = 100
for ($i = 0; $i -lt 4; $i++) {
  $fill = $C.card; $lc = $C.line; if ($i -eq 3) { $fill = $C.warnbg; $lc = $C.warn }
  Add-Rect $s $x $y $bw 158 $fill 0.06 $lc | Out-Null
  Add-Circle $s ($x + 14) ($y + 14) 30 $C.brown $caps[$i][0] $C.white | Out-Null
  Add-Text $s $caps[$i][1] ($x + 54) ($y + 17) ($bw - 64) 26 16 $C.ink $MSO_TRUE $HEAD 1 1 | Out-Null
  Add-Body $s $caps[$i][2] ($x + 14) ($y + 56) ($bw - 28) 96 12 $C.ink | Out-Null
  $x += $bw + $gapx
}
Add-Body $s "The problem statement's four capabilities, in its own words." $M 264 ($W - 2 * $M) 16 10 $C.mfg | Out-Null
$stats = @(@("~4 min", "to check one SI/BL pair manually - seven fields, two documents"), @("~20 s", "to triage one email in a shared inbox of five kinds of mail"), @("1 field", "missed becomes a correction, a delay, rework"))
$x = $M
foreach ($st in $stats) {
  Add-Text $s $st[0] $x 290 270 44 32 $C.brown $MSO_TRUE $HEAD 1 1 | Out-Null
  Add-Body $s $st[1] $x 334 262 40 12.5 $C.ink | Out-Null
  $x += 294
}
Add-Body $s "Our own estimate, not a measurement." $M 376 400 16 10 $C.mfg | Out-Null
Add-Rect $s $M 404 ($W - 2 * $M) 70 $C.warnbg 0.12 $null | Out-Null
Add-Text $s "The fourth case" ($M + 18) 414 300 20 13 $C.warn $MSO_TRUE $BODY 1 1 | Out-Null
Add-Body $s "Sometimes the check cannot be done: a scan with no text layer, a blank field, the wrong document. That goes to a person with the reason and the next step. It is never guessed." ($M + 18) 434 ($W - 2 * $M - 36) 36 13 $C.ink | Out-Null
Add-Tag $s "Rubric 5 · Solution effectiveness & user value · 10" $false | Out-Null
Set-Notes $s "SPEAKER A (Yee Teng) · 0:15-0:50`r`rWhy we built it. A shipping desk gets five kinds of email in one inbox. For every document check, a clerk compares the Shipping Instruction with the draft Bill of Lading - seven fields, manually. Our own estimate: about four minutes a pair. Miss one field and it becomes a correction, a delay, rework. And sometimes the check can't be done - a scan with no text, a blank field, the wrong document. That has to go to a person with the reason, not be guessed. Chye Fong.`r`r(Do NOT say eleven hours here - it is said once, live, on the Before Sentinel view.)"

# ============================================================ 3 · how it decides (B)
$s = New-Slide $pres $C.bg
Add-Kicker $s "How it decides" $false | Out-Null
Add-Title $s "Six stages, one direction - and a gate that can say no" $false | Out-Null
$stages = @("Classify", "Intake", "Extract", "Compare", "Evidence gate", "Decide")
$sw = 124; $sh = 46; $sg = 20; $x0 = $M + 4; $y = 118
for ($i = 0; $i -lt 6; $i++) {
  $x = $x0 + $i * ($sw + $sg)
  $fill = $C.card; $col = $C.ink; $lc = $C.line
  if ($i -eq 4) { $fill = $C.brown; $col = $C.white; $lc = $null }
  $r = Add-Rect $s $x $y $sw $sh $fill 0.2 $lc
  $tr = $r.TextFrame.TextRange; $tr.Text = ("" + ($i + 1) + "  " + $stages[$i]); $tr.Font.Name = $HEAD; $tr.Font.Size = [double]13.5; $tr.Font.Bold = [int]-1
  $tr.Font.Color.RGB = [int]$col; $tr.ParagraphFormat.Alignment = 2; $r.TextFrame.VerticalAnchor = 3
  if ($i -lt 5) { Add-Arrow $s ($x + $sw + 2) ($y + $sh / 2) ($x + $sw + $sg - 2) ($y + $sh / 2) $C.mfg 1.5 | Out-Null }
}
$gx = $x0 + 4 * ($sw + $sg); $cx = $x0 + 3 * ($sw + $sg)
$veto = $s.Shapes.AddLine([double]($gx + $sw / 2), [double]($y - 8), [double]($cx + $sw / 2), [double]($y - 8))
$veto.Line.ForeColor.RGB = [int]$C.warn; $veto.Line.Weight = [double]1.5; $veto.Line.EndArrowheadStyle = 2; $veto.Line.DashStyle = 4
Add-Text $s "can overrule the comparison" ($cx + $sw / 2) ($y - 26) ($gx - $cx) 14 10 $C.warn $MSO_TRUE $BODY 2 1 | Out-Null
Add-Body $s "No discrepancy · Discrepancy · Escalated + reason" ($x0 + 5 * ($sw + $sg) - 30) ($y + $sh + 4) ($sw + 40) 28 9.5 $C.mfg | Out-Null
$ai = Add-Rect $s $x0 ($y + $sh + 10) (3 * $sw + 2 * $sg) 40 $C.aibg 0.2 $null
Add-Text $s "Model tier (gpt-5-mini, structured output) - only where the rules can't read: an unclear email · a label never seen · a scanned page. Every answer must be found again in the document." ($x0 + 10) ($y + $sh + 14) (3 * $sw + 2 * $sg - 20) 34 10 $C.ai 0 $BODY 1 3 | Out-Null
$dec = @(
  @("Values exactly, never by similarity", "APRIL FINE PAPER TRADING and APRIL FINE PAPER TRADING (MIDDLE EAST) FZE are two different companies in this data. Labels are matched by meaning; values, exactly.", "Our cost: sometimes a person checks a pair that was fine. The alternative's cost: a wrong Bill of Lading, cleared silently."),
  @("Rules first, model second", "The model is asked only where the rules admit they cannot read, and every case records which one answered.", "Cost: with the model tier off, a label we have never seen is escalated, not read."),
  @("One stateless library", "No web server or database inside the pipeline. The API, the command line and the tests run the same code, so what is scored is what you see.", "Cost: no database yet - reviews live in memory until the one-file change.")
)
$cw = 277; $x = $M; $y2 = 236
for ($i = 0; $i -lt 3; $i++) {
  Add-Rect $s $x $y2 $cw 160 $C.card 0.05 $C.line | Out-Null
  Add-Text $s $dec[$i][0] ($x + 14) ($y2 + 12) ($cw - 28) 22 13.5 $C.ink $MSO_TRUE $HEAD 1 1 | Out-Null
  Add-Body $s $dec[$i][1] ($x + 14) ($y2 + 38) ($cw - 28) 70 11.5 $C.ink | Out-Null
  Add-Body $s $dec[$i][2] ($x + 14) ($y2 + 108) ($cw - 28) 48 10.5 $C.warn | Out-Null
  $x += $cw + 14
}
Add-Rect $s $M 408 ($W - 2 * $M) 72 $C.muted 0.1 $null | Out-Null
Add-Bold $s "Deployed and scaling, as built" ($M + 16) 416 400 18 11.5 $C.brown | Out-Null
Add-Body $s "Vercel (Next.js dashboard)  ->  Render (FastAPI + the pipeline, one Docker container, non-root user)  ->  OpenAI.   Under 3 ms per email on one laptop core. All state sits behind one class (store.py): a database is a one-file change, then throughput is more copies of the same container." ($M + 16) 436 ($W - 2 * $M - 32) 40 11 $C.ink | Out-Null
Add-Tag $s "Rubric 2 · Architecture & scalability · 15" $false | Out-Null
Set-Notes $s "SPEAKER B (Chye Fong) · 0:50-1:50`r`rSix stages, one direction. The unusual one is the gate: it runs after the comparison and can overrule it. If a value can't be found again in its own document, we don't report a discrepancy - we escalate. Three decisions, each with a cost. One: values are compared exactly, never by similarity - this data has APRIL FINE PAPER TRADING, and the same name with MIDDLE EAST: two different companies. Our cost: sometimes a person checks a pair that was fine. The alternative's cost: a wrong Bill of Lading, cleared silently. Two: rules first, the model only where rules can't read - and every case records which one answered. Three: one stateless library - the API, the command line and the tests run the same code. So scaling is more copies; state sits behind one class, and a database is a one-file change. Let's watch it run."

# ============================================================ 4 · demo map (B -> A)
$s = New-Slide $pres $C.dbg
Add-Kicker $s "Live demo · 6 minutes · on the deployed site" $true | Out-Null
Add-Title $s "What to watch for" $true | Out-Null
$cols = @(
  @("Chye Fong  ·  how it works", @(
    @("1", "The whole inbox - 520 emails, model tier on, live on the cloud", "End-to-end · Technology"),
    @("2", "Before Sentinel / With Sentinel - the inbox as a clerk gets it", "Effectiveness"),
    @("3", "One case through the six stages - the line under every value", "Architecture"),
    @("4", "Compare: model off, then on - it escalates, then it reads", "Technology · Robustness"))),
  @("Yee Teng  ·  how a reviewer uses it", @(
    @("5", "Patterns across the inbox -> this shipper's history on the field", "Differentiation"),
    @("6", "Edit a value -> compared again -> reply drafted from the decision", "User experience"),
    @("7", "A scan: the transcription is evidence, never a verdict", "Technology · Robustness"),
    @("8", "Amended documents arrive -> the same check runs again", "End-to-end")))
)
$x = $M
foreach ($col in $cols) {
  Add-Rect $s $x 96 424 360 $C.dcard 0.04 $null | Out-Null
  Add-Text $s $col[0] ($x + 18) 110 390 20 14 $C.dgold $MSO_TRUE $BODY 1 1 | Out-Null
  $y = 146
  foreach ($it in $col[1]) {
    Add-Circle $s ($x + 18) $y 26 $C.dgold $it[0] $C.dbg | Out-Null
    Add-Body $s $it[1] ($x + 56) ($y - 1) 352 36 13 $C.dfg | Out-Null
    Add-Body $s $it[2] ($x + 56) ($y + 36) 352 16 10 $C.dmfg | Out-Null
    $y += 76
  }
  $x += 424 + 16
}
Add-Body $s "If the venue network fails: the same inbox runs on the laptop with no network at all - only the model beats change. Screenshots of every beat follow the closing slide." $M 468 ($W - 2 * $M) 30 11 $C.dmfg | Out-Null
Set-Notes $s "SPEAKER B (Chye Fong) drives the laptop for the whole demo. Full click-by-click script: docs/PITCH_DAY.md, 'The ten minutes'.`r`r1:50-2:40 (B) Run the inbox, model tier TICKED. 2:40-3:00 (B) Before / With Sentinel. 3:00-3:50 (B) email_004 through the stages, open '1 note from Sentinel'. 3:50-4:50 (B) Compare, 'Labels we have never seen', off then on - say 168 -> 2 here.`r`r4:50-7:55 (A speaks, B clicks) Patterns -> email_031 -> history, View original, Edit BL gross weight, Draft reply; email_512 scan transcription; email_506 re-check; one sentence on common alternatives.`r`rCheckpoints: run page done by 2:40 · handover to A by 4:55 · re-check done by 7:45."

# ============================================================ 5 · how we know it holds (B)
$s = New-Slide $pres $C.bg
Add-Kicker $s "What a demo can't show" $false | Out-Null
Add-Title $s "How we know it holds" $false | Out-Null
$cards = @(
  @("Not memorised", "1.0000 on the organisers' scorer - and on three more datasets from seeds we never developed against. 225 planted discrepancies, each caught with the exact field set; 80 of 80 escalations correct."),
  @("Attacked ourselves", "16 kinds of damage, 3,008 perturbed documents, 20,496 field reads, no answer key. 13 kinds change nothing; 0 invented discrepancies in any. Under OCR damage, silently wrong values: 982 -> 0."),
  @("Outside the organisers' data", "Real carrier forms, real scans, archived bills of lading, 14,326 real emails. It cannot read most real form layouts yet - and made 0 wrong automatic decisions: every one went to a person."),
  @("Engineering", "757 tests, 0 failing; CI on every push to main. Runs with no key and no network. A `$2 model cap per run - when it is spent, hard cases escalate. The container runs as a non-root user with no secret inside.")
)
$cw = 272; $ch = 158
for ($i = 0; $i -lt 4; $i++) {
  $cx = $M + ($i % 2) * ($cw + 14); $cy = 96 + [math]::Floor($i / 2) * ($ch + 14)
  Add-Rect $s $cx $cy $cw $ch $C.card 0.05 $C.line | Out-Null
  Add-Text $s $cards[$i][0] ($cx + 14) ($cy + 12) ($cw - 28) 22 14 $C.ink $MSO_TRUE $HEAD 1 1 | Out-Null
  Add-Body $s $cards[$i][1] ($cx + 14) ($cy + 40) ($cw - 28) 112 11.5 $C.ink | Out-Null
}
$hx = $M + 2 * ($cw + 14) + 2; $hw = $W - $M - $hx
Add-Rect $s $hx 96 $hw 330 $C.warnbg 0.05 $null | Out-Null
Add-Text $s "What we haven't fixed" ($hx + 14) 108 ($hw - 28) 22 14 $C.warn $MSO_TRUE $HEAD 1 1 | Out-Null
Add-Body $s "email_145: a wrapped party name cut to exactly what the other document says. One real discrepancy in 3,008 perturbed documents is reported as consistent.`r`rThe obvious guard would flag 114 of 124 SI/BL pairs (92%) - worse than the gap. So it stays open, and written down." ($hx + 14) 138 ($hw - 28) 210 11.5 $C.ink | Out-Null
Add-Text $s "A defect we hide is worse than one we miss." ($hx + 14) 262 ($hw - 28) 44 12 $C.warn $MSO_TRUE $HEAD 1 1 | Out-Null
Add-Body $s "Also written down: most real form layouts are not read yet; no database, accounts or mailbox connector yet." ($hx + 14) 330 ($hw - 28) 80 10.5 $C.mfg | Out-Null
Add-Body $s "A perfect score on the data you were handed proves you didn't memorise it - not that the reader works. So we went looking for the failures ourselves." $M 448 ($W - 2 * $M) 34 11.5 $C.mfg | Out-Null
Add-Tag $s "Rubric 4 · Engineering quality & robustness · 15" $false | Out-Null
Set-Notes $s "SPEAKER B (Chye Fong) · 7:55-8:50`r`rWhat a demo can't show: how we know it holds. 1.0000 on the organisers' scorer - and on three more datasets from seeds we never developed against. But a perfect score on the data you were handed doesn't prove the reader works. So we damaged our own documents: sixteen kinds of damage, 3,008 documents, no answer key. Thirteen change nothing; under OCR damage, silently wrong values went from 982 to zero. Then real documents from outside that data - carrier forms, scans, fourteen thousand emails. It can't read most real layouts yet, and it made zero wrong automatic decisions: what it couldn't read went to a person. 757 tests on every push to main. And the one we haven't fixed is on the slide - a defect we hide is worse than one we miss. Yee Teng."

# ============================================================ 6 · impact (A)
$s = New-Slide $pres $C.bg
Add-Kicker $s "Impact" $false | Out-Null
Add-Title $s "One desk first - and three numbers to hold" $false | Out-Null
Add-Body $s "The inbox already carries four desk codes: AFEMY 35 · AIE 30 · AFRT 29 · AFPTME 22 emails. Sentinel runs beside one desk's existing check until these hold for a full cycle of its carriers:" $M 90 530 44 12.5 $C.ink | Out-Null
$tblShape = $s.Shapes.AddTable(4, 3, [double]$M, [double]144, [double]530, [double]150)
$tbl = $tblShape.Table
$cells = @(
  @("Measure", "Today, on this inbox", "The pilot watches"),
  @("Escalation rate", "20 of 220 requests (9.1%), every one correct", "that it stays correct as new templates arrive"),
  @("False discrepancies", "0 of 46", "the weekly number"),
  @("Reviewer minutes per escalation", "not measured yet", "the pilot's first new measurement")
)
for ($ri = 1; $ri -le 4; $ri++) { for ($ci = 1; $ci -le 3; $ci++) {
  $cellShape = $tbl.Cell($ri, $ci).Shape
  $tr = $cellShape.TextFrame.TextRange
  $tr.Text = $cells[$ri - 1][$ci - 1]; $tr.Font.Size = [double]11; $tr.Font.Name = $BODY; $tr.Font.Color.RGB = [int]$C.ink; $tr.Font.Bold = [int]0
  $cellShape.Fill.Solid()
  if ($ri -eq 1) { $tr.Font.Bold = [int]-1; $tr.Font.Color.RGB = [int]$C.white; $cellShape.Fill.ForeColor.RGB = [int]$C.brown }
  else { $cellShape.Fill.ForeColor.RGB = [int]$C.card }
} }
$tbl.Columns.Item(1).Width = [double]165; $tbl.Columns.Item(2).Width = [double]195; $tbl.Columns.Item(3).Width = [double]170
Add-Body $s "Cost: on this inbox the rules decide every email, so a run costs nothing. Where the model is needed: `$0.0013 per document (measured), with a `$2 cap per run." $M 312 530 36 12 $C.ink | Out-Null
Add-Rect $s $M 364 530 70 $C.okbg 0.1 $null | Out-Null
Add-Bold $s "Built since round one" ($M + 14) 372 500 18 12 $C.ok | Out-Null
Add-Body $s "Pattern alerts across the inbox, and throughput and cost at volume - two of the five items on our round-one roadmap, now live." ($M + 14) 392 500 38 12 $C.ink | Out-Null
Add-Rect $s 602 90 310 344 $C.card 0.05 $C.line | Out-Null
Add-Text $s "Next, in order" 618 104 280 22 15 $C.ink $MSO_TRUE $HEAD 1 1 | Out-Null
$next = @(
  @("1", "Per-desk rules", "a label table and an escalation policy per desk, picked by the desk code the inbox already carries"),
  @("2", "Corrections feed the label table", "every confirmed correction is a labelled example of wording we could not read - the one place this system should learn"),
  @("3", "The database, then accounts", "one file for the store; accounts and a mailbox connector after it")
)
$y = 142
foreach ($n in $next) {
  Add-Circle $s 618 $y 26 $C.brown $n[0] $C.white | Out-Null
  Add-Bold $s $n[1] 654 ($y - 1) 246 20 13 $C.ink | Out-Null
  Add-Body $s $n[2] 654 ($y + 20) 246 70 11 $C.mfg | Out-Null
  $y += 96
}
Add-Tag $s "Rubric 7 · Impact & future potential · 10" $false | Out-Null
Set-Notes $s "SPEAKER A (Yee Teng) · 8:50-9:45`r`rImpact. The first user is one documentation desk - the inbox already carries four desk codes. Sentinel runs beside that desk's existing check until three numbers hold: the escalation rate - nine percent today, every one correct; false discrepancies - zero of forty-six; and reviewer minutes per escalation - which the pilot is there to measure. Cost: on this inbox the rules decide every email, so a run costs nothing; where the model is needed it's about a tenth of a cent per document, with a two-dollar cap per run. Next, in order: per-desk rules; confirmed reviewer corrections feed the label table - the one place this system should learn; then the database. And two items from our round-one roadmap - pattern alerts and cost at volume - are already built."

# ============================================================ 7 · close (A)
$s = New-Slide $pres $C.dbg
Add-Text $s "Every answer comes with its evidence." $M 118 ($W - 2 * $M) 56 36 $C.dfg $MSO_TRUE $HEAD 2 3 | Out-Null
Add-Text $s "Sentinel, by DuoCode" $M 182 ($W - 2 * $M) 28 18 $C.dgold 0 $HEAD 2 1 | Out-Null
# Wording checked against the other finalists' public code on 25 Sep: none of
# these three claims "only us" - each is simply true of Sentinel as worded.
$keep = @(
  @("Every value found again in its document", "rule-read or model-read, before any verdict is reported"),
  @("Attacked by its own authors", "3,008 damaged documents, no answer key - the failures published, one still open"),
  @("Tested outside the organisers' data", "real forms, real scans, real emails - what it couldn't read went to a person")
)
$x = $M + 10
foreach ($k in $keep) {
  Add-Rect $s $x 250 272 104 $C.dcard 0.06 $null | Out-Null
  Add-Text $s $k[0] ($x + 14) 262 244 40 13.5 $C.dgold $MSO_TRUE $HEAD 1 1 | Out-Null
  Add-Body $s $k[1] ($x + 14) 304 244 44 11.5 $C.dfg | Out-Null
  $x += 272 + 14
}
Add-Text $s "duocode-sentinel.vercel.app  ·  github.com/TCF1209/duocode-sentinel" $M 390 ($W - 2 * $M) 22 13 $C.dmfg 0 $BODY 2 1 | Out-Null
Add-Text $s "Thank you - questions welcome." $M 430 ($W - 2 * $M) 24 15 $C.dfg 0 $HEAD 2 1 | Out-Null
Set-Notes $s "SPEAKER A (Yee Teng) · 9:45-10:00`r`rSentinel, by DuoCode. The whole inbox, live on the cloud; the model where rules can't read; a person in charge of anything it can't prove. Every answer comes with its evidence. Thank you."

# ============================================================ backup · the demo in screenshots (hidden on stage, in the PDF)
$backup = @(
  @("1 · The whole inbox, one run", "520 emails sorted into five kinds of mail; 46 discrepancies and 20 escalations, each with its reason; 6 model calls, all scanned pages.", @("run_page.png")),
  @("2 · Before Sentinel", "The same inbox as a clerk receives it: 124 SI/BL pairs among 520 emails, about 11.2 hours at our own estimate.", @("run_before.png")),
  @("3 · One case through the stages", "Both documents identified; under every value, the document, the line and the label as printed ('To the Order of' read as Consignee); the gate's note: every compared value (14/14) was located in its source document.", @("case_004_gate.png")),
  @("4 · Compare: model off, then on", "Left: unfamiliar labels, rules only - escalated, with the fields it could not read. Right: the model reads them, each value re-found in the document - 'Model answered'.", @("compare_off.png", "compare_on.png")),
  @("5 · Patterns across the inbox", "The six largest of 21 patterns; the top one is seven cases from one shipper with a discrepancy on gross weight.", @("run_patterns.png")),
  @("6 · Shipper history, and a value corrected in place", "Left: same shipper, same field - other cases in this run. Right: the BL weight edited by the reviewer, compared again by the same rules, the extracted value kept struck through.", @("case_031_history.png", "case_031_edit.png")),
  @("7 · The reply follows the reviewer's decision", "After the correction it asks only about the container count. The facts are locked; only the greeting and closing may be reworded by the model.", @("reply_draft.png")),
  @("8 · A scan: transcription is evidence, not a verdict", "No text layer, so Sentinel did not decide. The model's transcription is shown for the reviewer to check against the image; here it misread 'AL GURG' as 'ALGURG' on the BL - which is exactly why a person ticks what was verified.", @("scan_512.png", "scan_512_accept.png")),
  @("9 · Amended documents, the same check again", "An email whose attachments were dropped: the amended pair is attached on the case, the check runs again, and the earlier result stays on record as version 1.", @("recheck_506.png"))
)
foreach ($b in $backup) {
  $s = New-Slide $pres $C.bg
  Add-Kicker $s "Demo backup - shown only if the live demo cannot run" $false | Out-Null
  Add-Text $s $b[0] $M 32 ($W - 2 * $M) 30 22 $C.ink $MSO_TRUE $HEAD 1 3 | Out-Null
  Add-Body $s $b[1] $M 68 ($W - 2 * $M) 34 12 $C.mfg | Out-Null
  $imgs = $b[2]
  if ($imgs.Count -eq 1) { Add-Pic $s ("$SHOTS\" + $imgs[0]) 144 110 672 410 | Out-Null }
  else {
    Add-Pic $s ("$SHOTS\" + $imgs[0]) $M 118 426 400 | Out-Null
    Add-Pic $s ("$SHOTS\" + $imgs[1]) ($M + 438) 118 426 400 | Out-Null
  }
  Hide-Slide $s
  Set-Notes $s "Hidden in the slide show. Use only if both the deployed site and the laptop fallback fail: right-click > See all slides, or type the slide number and Enter."
}

# ============================================================ save + render
if (Test-Path $OUT_PPTX) { Remove-Item $OUT_PPTX -Force }
if (Test-Path $OUT_PDF)  { Remove-Item $OUT_PDF -Force }
if (Test-Path $PNG_DIR)  { Remove-Item $PNG_DIR -Recurse -Force }
$pres.SaveAs($OUT_PPTX)
$pres.Export($PNG_DIR, "PNG", 1920, 1080)
# The PDF keeps the backup slides: unhide them for the PDF only, then close
# without saving, so the .pptx on disk still skips them in the slide show.
# (ExportAsFixedFormat's PrintHiddenSlides cannot be passed from PowerShell.)
foreach ($sl in $pres.Slides) { $sl.SlideShowTransition.Hidden = 0 }
$pres.SaveAs($OUT_PDF, 32)
$pres.Saved = -1
$pres.Close(); $app.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
Write-Output ("slides: " + (Get-ChildItem $PNG_DIR | Measure-Object).Count)
Get-Item $OUT_PPTX, $OUT_PDF | Select-Object Name, Length | Format-Table -AutoSize
