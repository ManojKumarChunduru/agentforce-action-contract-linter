/**
 * Helper for CaseSummarizer. Has no @InvocableMethod, so it is a target the linter
 * must refuse if an action ever points at it.
 */
public with sharing class SummaryUtil {
    public static String firstSentences(Case c, Integer limitSentences) {
        String text = c.Subject + '. ' + (c.Description == null ? '' : c.Description);
        List<String> sentences = text.split('\\.\\s+');
        List<String> kept = new List<String>();
        for (Integer i = 0; i < sentences.size() && i < limitSentences; i++) {
            kept.add(sentences[i]);
        }
        return String.join(kept, '. ');
    }
}
