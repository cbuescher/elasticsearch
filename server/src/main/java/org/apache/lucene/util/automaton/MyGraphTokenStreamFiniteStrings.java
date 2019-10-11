package org.apache.lucene.util.automaton;

import org.apache.lucene.analysis.TokenStream;
import org.apache.lucene.analysis.tokenattributes.CharTermAttribute;
import org.apache.lucene.analysis.tokenattributes.PositionIncrementAttribute;
import org.apache.lucene.analysis.tokenattributes.PositionLengthAttribute;
import org.apache.lucene.analysis.tokenattributes.TermToBytesRefAttribute;
import org.apache.lucene.index.Term;
import org.apache.lucene.util.ArrayUtil;
import org.apache.lucene.util.AttributeSource;
import org.apache.lucene.util.IntsRef;

import java.io.IOException;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.BitSet;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;

import static org.apache.lucene.util.automaton.Operations.DEFAULT_MAX_DETERMINIZED_STATES;

/**
 * Consumes a TokenStream and creates an {@link Automaton} where the transition labels are terms from
 * the {@link TermToBytesRefAttribute}.
 * This class also provides helpers to explore the different paths of the {@link Automaton}.
 */
public final class MyGraphTokenStreamFiniteStrings {

  private AttributeSource[] tokens = new AttributeSource[4];
  public final Automaton det;
  private final Transition transition = new Transition();

  private class FiniteStringsTokenStream extends TokenStream {
    private final IntsRef ids;
    private final int end;
    private int offset;

    FiniteStringsTokenStream(final IntsRef ids) {
      super(tokens[0].cloneAttributes());
      assert ids != null;
      this.ids = ids;
      this.offset = ids.offset;
      this.end = ids.offset + ids.length;
    }

    @Override
    public boolean incrementToken() throws IOException {
      if (offset < end) {
        clearAttributes();
        int id = ids.ints[offset];
        tokens[id].copyTo(this);
        offset++;
        return true;
      }

      return false;
    }
  }

  public MyGraphTokenStreamFiniteStrings(TokenStream in) throws IOException {
    Automaton aut = build(in);
    System.out.println("Automaton BEFORE determinization:");
    System.out.println("Live states: " + getLiveStatesFromInitial(aut));
    System.out.println("Live states to accept: " + getLiveStatesToAccept(aut));
    System.out.println("Number of states: " + aut.getNumStates());
    dumpAutomaton(aut);
    System.out.println("------");
    Automaton determinize = Operations.determinize(aut, DEFAULT_MAX_DETERMINIZED_STATES);
    System.out.println("Automaton AFTER determinization:");
    System.out.println("Live states: " + getLiveStatesFromInitial(determinize));
    System.out.println("Live states to accept: " + getLiveStatesToAccept(determinize));
    System.out.println("Number of states: " + determinize.getNumStates());
    dumpAutomaton(determinize);
    System.out.println("------");
    this.det = Operations.removeDeadStates(determinize);
    System.out.println("Number of states after removal of dead states: " + det.getNumStates());
  }

    private void dumpAutomaton(Automaton aut) {
        System.out.println("Dumping automaton");
        Transition[][] sortedTransitions = aut.getSortedTransitions();
        for (int i = 0; i < sortedTransitions.length; i++) {
            System.out.println(i + ":");
            for (int j = 0; j < sortedTransitions[i].length; j++) {
                System.out.println(sortedTransitions[i][j]);
            }
        }
    }

  /**
   * Returns the set of live states. A state is "live" if an accept state is
   * reachable from it and if it is reachable from the initial state.
   */
  private static BitSet getLiveStates(Automaton a) {
    BitSet live = getLiveStatesFromInitial(a);
    live.and(getLiveStatesToAccept(a));
    return live;
  }

  /** Returns bitset marking states reachable from the initial state. */
  private static BitSet getLiveStatesFromInitial(Automaton a) {
    int numStates = a.getNumStates();
    BitSet live = new BitSet(numStates);
    if (numStates == 0) {
      return live;
    }
    ArrayDeque<Integer> workList = new ArrayDeque<>();
    live.set(0);
    workList.add(0);

    Transition t = new Transition();
    while (workList.isEmpty() == false) {
      int s = workList.removeFirst();
      int count = a.initTransition(s, t);
      for(int i=0;i<count;i++) {
        a.getNextTransition(t);
        if (live.get(t.dest) == false) {
          live.set(t.dest);
          workList.add(t.dest);
        }
      }
    }

    return live;
  }

  /** Returns bitset marking states that can reach an accept state. */
  private static BitSet getLiveStatesToAccept(Automaton a) {
    Automaton.Builder builder = new Automaton.Builder();

    // NOTE: not quite the same thing as what SpecialOperations.reverse does:
    Transition t = new Transition();
    int numStates = a.getNumStates();
    for(int s=0;s<numStates;s++) {
      builder.createState();
    }
    for(int s=0;s<numStates;s++) {
      int count = a.initTransition(s, t);
      for(int i=0;i<count;i++) {
        a.getNextTransition(t);
        builder.addTransition(t.dest, s, t.min, t.max);
      }
    }
    Automaton a2 = builder.finish();

    ArrayDeque<Integer> workList = new ArrayDeque<>();
    BitSet live = new BitSet(numStates);
    BitSet acceptBits = a.getAcceptStates();
    int s = 0;
    while (s < numStates && (s = acceptBits.nextSetBit(s)) != -1) {
      live.set(s);
      workList.add(s);
      s++;
    }

    while (workList.isEmpty() == false) {
      s = workList.removeFirst();
      int count = a2.initTransition(s, t);
      for(int i=0;i<count;i++) {
        a2.getNextTransition(t);
        if (live.get(t.dest) == false) {
          live.set(t.dest);
          workList.add(t.dest);
        }
      }
    }

    return live;
  }

  /**
   * Returns whether the provided state is the start of multiple side paths of different length (eg: new york, ny)
   */
  public boolean hasSidePath(int state) {
    int numT = det.initTransition(state, transition);
    if (numT <= 1) {
      return false;
    }
    det.getNextTransition(transition);
    int dest = transition.dest;
    for (int i = 1; i < numT; i++) {
      det.getNextTransition(transition);
      if (dest != transition.dest) {
        return true;
      }
    }
    return false;
  }

  /**
   * Returns the list of tokens that start at the provided state
   */
  public List<AttributeSource> getTerms(int state) {
    int numT = det.initTransition(state, transition);
    List<AttributeSource> tokens = new ArrayList<> ();
    for (int i = 0; i < numT; i++) {
      det.getNextTransition(transition);
      tokens.addAll(Arrays.asList(this.tokens).subList(transition.min, transition.max + 1));
    }
    return tokens;
  }

  /**
   * Returns the list of terms that start at the provided state
   */
  public Term[] getTerms(String field, int state) {
    return getTerms(state).stream()
        .map(s -> new Term(field, s.addAttribute(TermToBytesRefAttribute.class).getBytesRef()))
        .toArray(Term[]::new);
  }

  /**
   * Get all finite strings from the automaton.
   */
  public Iterator<TokenStream> getFiniteStrings() throws IOException {
    return getFiniteStrings(0, -1);
  }


  /**
   * Get all finite strings that start at {@code startState} and end at {@code endState}.
   */
  public Iterator<TokenStream> getFiniteStrings(int startState, int endState) {
    final FiniteStringsIterator it = new FiniteStringsIterator(det, startState, endState);
    return new Iterator<TokenStream> () {
      IntsRef current;
      boolean finished = false;

      @Override
      public boolean hasNext() {
        if (finished == false && current == null) {
          current = it.next();
          if (current == null) {
            finished = true;
          }
        }
        return current != null;
      }

      @Override
      public TokenStream next() {
        if (current == null) {
          hasNext();
        }
        TokenStream next =  new FiniteStringsTokenStream(current);
        current = null;
        return next;
      }
    };
  }

  /**
   * Returns the articulation points (or cut vertices) of the graph:
   * https://en.wikipedia.org/wiki/Biconnected_component
   */
  public int[] articulationPoints() {
    if (det.getNumStates() == 0) {
      return new int[0];
    }
    //
    Automaton.Builder undirect = new Automaton.Builder();
    undirect.copy(det);
    for (int i = 0; i < det.getNumStates(); i++) {
      int numT = det.initTransition(i, transition);
      for (int j = 0; j < numT; j++) {
        det.getNextTransition(transition);
        undirect.addTransition(transition.dest, i, transition.min);
      }
    }
    int numStates = det.getNumStates();
    BitSet visited = new BitSet(numStates);
    int[] depth = new int[det.getNumStates()];
    int[] low = new int[det.getNumStates()];
    int[] parent = new int[det.getNumStates()];
    Arrays.fill(parent, -1);
    List<Integer> points = new ArrayList<>();
    articulationPointsRecurse(undirect.finish(), 0, 0, depth, low, parent, visited, points);
    Collections.reverse(points);
    return points.stream().mapToInt(p -> p).toArray();
  }

  /**
   * Build an automaton from the provided {@link TokenStream}.
   */
  private Automaton build(final TokenStream in) throws IOException {
    Automaton.Builder builder = new Automaton.Builder();

    final PositionIncrementAttribute posIncAtt = in.addAttribute(PositionIncrementAttribute.class);
    final PositionLengthAttribute posLengthAtt = in.addAttribute(PositionLengthAttribute.class);
    final CharTermAttribute charAtt = in.addAttribute(CharTermAttribute.class);

    in.reset();

    int pos = -1;
    int prevIncr = 1;
    int state = -1;
    int id = -1;
    int gap = 0;
    int prevPositionLength = -1;
    while (in.incrementToken()) {
        System.out.println("token: " + charAtt.toString());
      int currentIncr = posIncAtt.getPositionIncrement();
      if (pos == -1 && currentIncr < 1) {
        throw new IllegalStateException("Malformed TokenStream, start token can't have increment less than 1");
      }

      if (currentIncr == 0) {
        if (gap > 0) {
          pos -= gap;
        }
      }
      else {
          if (currentIncr > 1 && currentIncr == prevPositionLength) {
              pos += currentIncr;
          } else {
              pos++;
              gap = currentIncr - 1;
          }
      }

      int endPos = pos + posLengthAtt.getPositionLength() + gap;
      prevPositionLength = posLengthAtt.getPositionLength();
      System.out.println("endPos: " + endPos);
      while (state < endPos) {
        state = builder.createState();
        // builder.setAccept(state, true);
        System.out.println("create state: " + state);
      }

      id++;
      if (tokens.length < id + 1) {
        tokens = ArrayUtil.grow(tokens, id + 1);
      }

      tokens[id] = in.cloneAttributes();
      builder.addTransition(pos, endPos, id);
      System.out.println("add transition: source=" + pos + ", dest=" + endPos + ", label=" + id);
      pos += gap;

      // we always produce linear token graphs from getFiniteStrings(), so we need to adjust
      // posLength and posIncrement accordingly
      tokens[id].addAttribute(PositionLengthAttribute.class).setPositionLength(1);
      if (currentIncr == 0) {
        // stacked token should have the same increment as original token at this position
        tokens[id].addAttribute(PositionIncrementAttribute.class).setPositionIncrement(prevIncr);
      }

      // only save last increment on non-zero increment in case we have multiple stacked tokens
      if (currentIncr > 0) {
        prevIncr = currentIncr;
      }
    }

    in.end();
    if (state != -1) {
        System.out.println("-> accept state " + state);
      builder.setAccept(state, true);
    }
    return builder.finish();
  }

  private static void articulationPointsRecurse(Automaton a, int state, int d, int[] depth, int[] low, int[] parent,
                                                BitSet visited, List<Integer> points) {
    visited.set(state);
    depth[state] = d;
    low[state] = d;
    int childCount = 0;
    boolean isArticulation = false;
    Transition t = new Transition();
    int numT = a.initTransition(state, t);
    for (int i = 0; i < numT; i++) {
      a.getNextTransition(t);
      if (visited.get(t.dest) == false) {
        parent[t.dest] = state;
        articulationPointsRecurse(a, t.dest, d + 1, depth, low, parent, visited, points);
        childCount++;
        if (low[t.dest] >= depth[state]) {
          isArticulation = true;
        }
        low[state] = Math.min(low[state], low[t.dest]);
      } else if (t.dest != parent[state]) {
        low[state] = Math.min(low[state], depth[t.dest]);
      }
    }
    if ((parent[state] != -1 && isArticulation) || (parent[state] == -1 && childCount > 1)) {
      points.add(state);
    }
  }
}