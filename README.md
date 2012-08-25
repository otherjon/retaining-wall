retaining-wall
==============

Software to generate draft engineering plans for segmental block retaining
walls.  IANACE.

So You Wanna Build A Retaining Wall...
--------------------------------------

Usually, if you want a retaining wall, you hire a contractor, or possibly
a contractor and a civil engineer if the wall is particularly large or
complicated.  But some walls are small enough for a handy homeowner to
build.  (Warning: There's "I can fix my toilet" handy, and there's "I can
rip open an exterior wall and frame a new bay window" handy.  Depending
on the specific needs, designing and building retaining walls is likely
to be closer to the latter.)

There are several types of retaining wall construction, including poured
concrete walls, soldier pile walls, segmental block walls, and others.
This software is tailored to segmental block walls, but may be useful for
other types as well.

This software is targeted at a user base of especially handy homeowners.  If
you are a licensed civil engineer, please contact the author -- you can
probably offer good advice on useful features that would make this software
more helpful.

Before You Begin
----------------

*Please check your local building codes* to determine
what kinds of walls can be built by a homeowner (you'll probably need a
building permit, at the very least) and what kinds of walls require a
licensed civil engineer's approval.  *THIS SOFTWARE WAS NOT WRITTEN BY A
LICENSED CIVIL ENGINEER.*  It is intended to help a homeowner estimate
the complexity of various wall designs, and to generate plans which can
then be reviewed, modified, and augmented by a civil engineer for less
effort and expense than creating plans from scratch.

What is a segmental block retaining wall?
-----------------------------------------

Instead of poured concrete or posts deep in the ground (the latter is
a "soldier pile wall"), some retaining walls are constructed from blocks
that resulted when a cinderblock and a Lego had a passionate night
together.  These "segmental blocks" are roughly the size of cinderblocks,
but shaped in such a way that they can be made to interlock.  They also
have connection points for "geogrid", which is like a mat of netting
designed to be embedded in the earth and grip it tightly.  If you bury
geogrid buried in the earth, the idea is that you can't pull it out
without pulling out a lot of earth with it.  If you have several layers
of geogrid near each other, then you can't pull any out without pulling
out the whole thing.  You see where this is going...

Consider a wall made of segmental blocks.  (Or cinderblocks, if you
prefer.)  It's pretty heavy, but enough earth pressure can tip it over.
Now consider attaching several layers of geogrid, 15 feet deep, to the
back of the wall.  Now the one-foot-thick wall and the 15-foot-thick
mass of earth behind it _act as a single integrated system_.  The retained
earth isn't pushing against a one-foot-thick wall -- it's pushing against
a 16-foot-thick mass of wall-and-earth, because those 15 feet of earth
are tied together (and tied to the wall) with geogrid.

Unless, of course, you haven't used enough geogrid.  Or the geogrid
ruptures.  Or pulls out of the earth.  Or maybe the whole thing slides.
Or imagine perfectly flat ground with no retaining wall needed, and a
two-foot-square chunk of nice solid concrete, and three dozen elephants
standing on each other's backs precariously balanced on that concrete --
you think the earth might squish?  (That's called "bearing capacity".)

So you need to design your retaining wall to resist several different
kinds of failure.

How do you know a particular retaining wall design is sufficient?
-----------------------------------------------------------------

In one sense, this is easy: You enumerate all the different ways that
the wall can fail.  In each case, you calculate the forces contributing
to failure, and you calculate the forces resisting failure.  (Sometimes
instead of forces we're interested in torques, a.k.a. "moments".)  In
each case, if the forces (or moments) resisting failure are greater than
the forces (moments) contributing to failure, and that excess meets a
certain safety margin (a multiplier called the _factor of safety_), then
that mode of failure won't occur -- or at least it won't occur under the
assumptions you've made.

That just leaves the problem of enumerating all the different ways that
the wall can fail, and calculating all those forces and moments.  And
that's where I hope my software can help you.

Getting started with the software
---------------------------------

When you install this repo, you'll have a directory called `sample-design`
available.  Try out the plan generator on that:
    ./Wall.py sample-design/config

That generates a LaTeX file, and it suggests a command to turn the result
into a PDF.  If you look at the resulting PDF, you'll see a lot of content
that you might want to change.  Take another look at the `sample-design`
directory.  It contains three files:
 * `config`, which just names the two other input parameter files and an
    output file
 * `PlansText`, which contains the static text included in the output (such
    as the project name and description)
 * `DesignParams-*`, which contains all the design parameters along with
    explanations of their meanings

Your next step is likely to be to copy the `sample-design` directory and
edit the files to start designing your own wall.  Good luck!
