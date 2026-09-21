Team photos for the intro screen of `/pitch`.

    tang-chye-fong.png             500 x 625   <- used, 4:5
    lim-yee-teng.webp              640 x 800   <- used, 4:5
    tang-chye-fong-original.png    312 x 312   as supplied
    lim-yee-teng-original.webp     960 x 1280  as supplied

The two in use are 4:5 crops of the originals, shown 112x140 on the card. The
originals are kept beside them so a crop can be redone or undone without asking
anyone for the files again.

Filenames, names and courses are the `TEAM` constant at the top of
`web/components/pitch-view.tsx` -- change them together. Keep filenames free of
spaces: a space becomes `%20` in the URL and is one more thing that can go wrong
between here and a deployed build.

A file the browser cannot load falls back to the person initials rather than a
broken-image icon, so the page stays presentable either way.
