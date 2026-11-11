/**
 * Reopens a closed case with a reason. Invoked by Reopen_Case, which no topic currently lists.
 */
public with sharing class CaseReopener {

    public class Request {
        @InvocableVariable(required=true label='Case Id')
        public Id caseId;
        @InvocableVariable(label='Reason')
        public String reason;
    }

    public class Response {
        @InvocableVariable(label='Reopened')
        public Boolean reopened;
    }

    @InvocableMethod(label='Reopen Case')
    public static List<Response> reopen(List<Request> requests) {
        List<Case> toUpdate = new List<Case>();
        for (Request r : requests) {
            toUpdate.add(new Case(Id = r.caseId, Status = 'Reopened'));
        }
        update toUpdate;
        List<Response> out = new List<Response>();
        for (Request r : requests) {
            Response resp = new Response();
            resp.reopened = true;
            out.add(resp);
        }
        return out;
    }
}
