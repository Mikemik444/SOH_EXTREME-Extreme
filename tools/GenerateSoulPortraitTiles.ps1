$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$JsonPath = Join-Path $Root 'tools\enemy-soul-assets.json'
$SourceDir = Join-Path $Root 'source\portraits'
$ContactPath = Join-Path $SourceDir 'portraits-contact.png'
$StalfosPath = Join-Path $SourceDir 'stalfos.png'
$OutDir = Join-Path $Root 'assets\custom\textures\parameter_static'

if (-not (Test-Path $JsonPath)) {
    throw "Missing $JsonPath"
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Add-Type -AssemblyName System.Drawing

$code = @'
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;

public static class SoulPortraitTileBuilder {
    private static Bitmap RemoveContactBackground(Bitmap src) {
        var dst = new Bitmap(src.Width, src.Height, PixelFormat.Format32bppArgb);
        int minX = src.Width, minY = src.Height, maxX = -1, maxY = -1;

        for (int y = 0; y < src.Height; ++y) {
            for (int x = 0; x < src.Width; ++x) {
                Color c = src.GetPixel(x, y);
                int d = Math.Max(Math.Abs(c.R - 25),
                        Math.Max(Math.Abs(c.G - 31), Math.Abs(c.B - 42)));
                if (d <= 2) {
                    dst.SetPixel(x, y, Color.Transparent);
                } else {
                    dst.SetPixel(x, y, Color.FromArgb(255, c.R, c.G, c.B));
                    if (x < minX) minX = x;
                    if (y < minY) minY = y;
                    if (x > maxX) maxX = x;
                    if (y > maxY) maxY = y;
                }
            }
        }

        if (maxX < minX || maxY < minY)
            return dst;

        Rectangle bounds = Rectangle.FromLTRB(minX, minY, maxX + 1, maxY + 1);
        Bitmap cropped = dst.Clone(bounds, PixelFormat.Format32bppArgb);
        dst.Dispose();
        return cropped;
    }

    private static Bitmap Make64(Bitmap model) {
        var canvas = new Bitmap(64, 64, PixelFormat.Format32bppArgb);
        using (Graphics g = Graphics.FromImage(canvas)) {
            g.Clear(Color.Transparent);
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.InterpolationMode = InterpolationMode.HighQualityBicubic;
            g.PixelOffsetMode = PixelOffsetMode.HighQuality;
            g.CompositingQuality = CompositingQuality.HighQuality;

            // Neutral dark backing improves silhouettes without hiding the enemy
            // behind the old giant skull/soul-base composite.
            using (var shadow = new SolidBrush(Color.FromArgb(105, 6, 10, 18)))
                g.FillEllipse(shadow, 2, 2, 60, 60);

            double scale = Math.Min(58.0 / model.Width, 58.0 / model.Height);
            int w = Math.Max(1, (int)Math.Round(model.Width * scale));
            int h = Math.Max(1, (int)Math.Round(model.Height * scale));
            int x = (64 - w) / 2;
            int y = (64 - h) / 2;

            // Soft light outline: draw the same sprite at neighboring offsets
            // with reduced alpha, then the full-color enemy at center.
            var ia = new ImageAttributes();
            var cm = new ColorMatrix(new float[][] {
                new float[] {0,0,0,0,0},
                new float[] {0,0,0,0,0},
                new float[] {0,0,0,0,0},
                new float[] {0,0,0,0.45f,0},
                new float[] {0.75f,0.88f,1.0f,0,1}
            });
            ia.SetColorMatrix(cm);
            foreach (var p in new Point[] {
                new Point(x-1,y), new Point(x+1,y), new Point(x,y-1), new Point(x,y+1)
            }) {
                g.DrawImage(model, new Rectangle(p.X,p.Y,w,h),
                            0,0,model.Width,model.Height,GraphicsUnit.Pixel,ia);
            }
            ia.Dispose();

            g.DrawImage(model, new Rectangle(x,y,w,h),
                        0,0,model.Width,model.Height,GraphicsUnit.Pixel);
        }
        return canvas;
    }

    public static void Build(string contactPath, string stalfosPath, string fallbackHq,
                             string key, int index, string outDir) {
        Bitmap model = null;
        try {
            if (key == "STALFOS" && File.Exists(stalfosPath)) {
                using (var src = new Bitmap(stalfosPath))
                    model = src.Clone(new Rectangle(0,0,src.Width,src.Height),
                                      PixelFormat.Format32bppArgb);
            } else if (File.Exists(contactPath)) {
                using (var sheet = new Bitmap(contactPath)) {
                    int x = (index % 8) * 140 + 4;
                    int y = (index / 8) * 156 + 4;
                    using (var raw = sheet.Clone(new Rectangle(x,y,132,123),
                                                 PixelFormat.Format32bppArgb))
                        model = RemoveContactBackground(raw);
                }
            } else if (File.Exists(fallbackHq)) {
                using (var src = new Bitmap(fallbackHq))
                    model = src.Clone(new Rectangle(0,0,src.Width,src.Height),
                                      PixelFormat.Format32bppArgb);
            } else {
                throw new FileNotFoundException("No portrait source for " + key);
            }

            using (model)
            using (var full = Make64(model)) {
                for (int i = 0; i < 4; ++i) {
                    int tx = (i % 2) * 32;
                    int ty = (i / 2) * 32;
                    using (var tile = full.Clone(new Rectangle(tx,ty,32,32),
                                                 PixelFormat.Format32bppArgb)) {
                        string outPath = Path.Combine(outDir,
                            "gExtremeSoulTile_" + key + "_" + i + ".rgba32.png");
                        tile.Save(outPath, ImageFormat.Png);
                    }
                }
            }
        } finally {
            if (model != null) model.Dispose();
        }
    }
}
'@

Add-Type -TypeDefinition $code -ReferencedAssemblies System.Drawing

$entries = Get-Content -Raw -LiteralPath $JsonPath | ConvertFrom-Json
for ($i = 0; $i -lt $entries.Count; ++$i) {
    $e = $entries[$i]
    $hq = Join-Path $OutDir ("gExtremeSoulHQ_{0}.rgba32.png" -f $e.key)
    [SoulPortraitTileBuilder]::Build(
        $ContactPath,
        $StalfosPath,
        $hq,
        [string]$e.key,
        $i,
        $OutDir
    )
    Write-Host ("  [{0,2}/{1}] {2}" -f ($i + 1), $entries.Count, $e.key)
}

$tiles = Get-ChildItem -LiteralPath $OutDir -Filter 'gExtremeSoulTile_*.rgba32.png'
$expected = $entries.Count * 4
if ($tiles.Count -ne $expected) {
    throw "Expected $expected soul portrait tiles, found $($tiles.Count)"
}

Write-Host ""
Write-Host "Generated $expected safe 32x32 soul portrait tiles." -ForegroundColor Green
Write-Host "The in-game renderer combines four tiles into one 64x64-detail portrait."
