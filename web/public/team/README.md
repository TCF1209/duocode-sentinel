Team photos for the intro screen of `/pitch`.

    tang-chye-fong.png             400 x 400   <- used
    lim-yee-teng.webp              400 x 400   <- used
    tang-chye-fong-original.png    312 x 312   as supplied
    lim-yee-teng-original.webp     960 x 1280  as supplied

The two in use are head-and-shoulders crops of the originals. At 44px a
half-body shot reads as a blob and a face reads as a person, which is the whole
argument; the originals are kept beside them so the crop can be redone or
undone without asking anyone for the files again.

Filenames are referenced by the `TEAM` constant at the top of
`web/components/pitch-view.tsx` -- change both together. Keep them free of
spaces: a space becomes `%20` in the URL and is one more thing that can go
wrong between here and a deployed build.

A file the browser cannot load falls back to the person's initials rather than
a broken-image icon, so the page stays presentable either way.
