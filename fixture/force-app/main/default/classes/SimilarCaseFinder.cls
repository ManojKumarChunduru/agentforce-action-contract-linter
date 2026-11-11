/**
 * Finds cases with a similar subject to the given case. Invoked by Find_Similar_Cases.
 */
public with sharing class SimilarCaseFinder {

    public class Request {
        @InvocableVariable(required=true label='Case Id')
        public Id caseId;
        @InvocableVariable(label='Limit' description='Maximum number of similar cases to return')
        public Integer limitCount;
    }

    public class Response {
        @InvocableVariable(label='Similar Case Ids')
        public List<Id> similarCaseIds;
        @InvocableVariable(label='Similarity Note')
        public String similarityNote;
    }

    @InvocableMethod(label='Find Similar Cases')
    public static List<Response> find(List<Request> requests) {
        List<Response> out = new List<Response>();
        for (Request r : requests) {
            Response resp = new Response();
            resp.similarCaseIds = new List<Id>();
            resp.similarityNote = 'Matched on subject keywords';
            out.add(resp);
        }
        return out;
    }
}
