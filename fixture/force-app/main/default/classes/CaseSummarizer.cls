/**
 * Builds a short plain-text summary of a case from its fields and recent comments.
 * Invoked by the Summarize_Case agent action. The caseId is typed Id on purpose so a
 * malformed value fails here rather than inside the SOQL bind.
 */
public with sharing class CaseSummarizer {

    public class Request {
        @InvocableVariable(required=true label='Case Id')
        public Id caseId;
        @InvocableVariable(label='Max Sentences' description='Upper bound on sentences in the summary')
        public Integer maxSentences;
    }

    public class Response {
        @InvocableVariable(label='Summary')
        public String summary;
    }

    @InvocableMethod(label='Summarize Case')
    public static List<Response> summarize(List<Request> requests) {
        Set<Id> ids = new Set<Id>();
        for (Request r : requests) {
            ids.add(r.caseId);
        }
        Map<Id, Case> cases = new Map<Id, Case>([
            SELECT Id, Subject, Status, Description FROM Case WHERE Id IN :ids
        ]);
        List<Response> out = new List<Response>();
        for (Request r : requests) {
            Response resp = new Response();
            Case c = cases.get(r.caseId);
            Integer limitSentences = r.maxSentences == null ? 3 : r.maxSentences;
            resp.summary = c == null ? '' : SummaryUtil.firstSentences(c, limitSentences);
            out.add(resp);
        }
        return out;
    }
}
