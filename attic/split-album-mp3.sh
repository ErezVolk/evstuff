#!/bin/sh

DOWNLOADED="Downloaded File.mp3"
ARTIST="Artist"
ALBUM="Album"
YEAR=1984

FOLDER="$ARTIST - $ALBUM"

curr=00:00
track() {
  if [ "$#" -ge 4 ]; then
    prev=$3
    curr=$4
  else
    prev=$curr
    curr=$3
  fi
  mp3splt -o "$FOLDER/$1 - $2" -g "[@a=$ARTIST,@b=$ALBUM,@t=$2,@y=$YEAR,@g=8,@n=$1]" "$DOWNLOADED" $(echo $prev |tr : .) $(echo $curr |tr : .)
  export curr
}

rm -Rfv "$FOLDER"
track 1 "Song" 00:00 04:57
open "$FOLDER"
