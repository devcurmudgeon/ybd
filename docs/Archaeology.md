## Archaeology

One of the stated aims of Baserock has been to ensure that old systems can be
reproduced a long time into the future (decades, for example).

Stating it doesn't make it true, though.

Originally the intention for ybd was to build definitions all the way back as
far as the move from morphs.git (2014-02-20). But the development of ybd
exposed some questionable assumptions in morph and in the definitions
themselves; we had never specified the definitions format, after all. In the
end it seemed more productive to fix the assumptions and move forward, rather
than make ybd repeat the mistakes.

For what it's worth, as of 2016-04-10 ybd parses all the way back to
baserock-14.40, which was the first tag where the morph files were organised
into subdirectories. Going back further could be attempted, if we consider it
worthwhile to exhume the builds further back.

This is how ybd behaves on various historical versions of ci.morph:

baserock-14.40:
  (no VERSION) stage1-gcc make[2]: *** [lto-compress.o] Error 1

baserock-15.10:
  (VERSION: 0) awk missing from m4-tarball definition, fixed at...

e77dd84ec11f0d:
  (VERSION: 1) configure.ac:29: error: xorg-macros version 1.18 or higher is required but 1.17 found

baserock-15.17-rc:
    (VERSION: 1) crashes on pygobject

baserock-15.19:
    (VERSION: 3) builds successfully
