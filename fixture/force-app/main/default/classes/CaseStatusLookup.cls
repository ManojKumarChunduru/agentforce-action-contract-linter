/**
 * Returns the current status of a case by its case number.
 * Invoked by the Get_Case_Status agent action.
 */
public with sharing class CaseStatusLookup {

    public class Request {
        @InvocableVariable(required=true label='Case Number' description='The human readable case number, for example 00001234')
        public String caseNumber;
    }

    public class Response {
        @InvocableVariable(label='Status')
        public String status;
        @InvocableVariable(label='Priority')
        public String priority;
        @InvocableVariable(label='Last Modified')
        public Datetime lastModified;
    }

    @InvocableMethod(label='Get Case Status' description='Look up a case by number and return its status')
    public static List<Response> getStatus(List<Request> requests) {
        List<Response> out = new List<Response>();
        Set<String> numbers = new Set<String>();
        for (Request r : requests) {
            numbers.add(r.caseNumber);
        }
        Map<String, Case> byNumber = new Map<String, Case>();
        for (Case c : [SELECT Id, CaseNumber, Status, Priority, LastModifiedDate
                       FROM Case WHERE CaseNumber IN :numbers]) {
            byNumber.put(c.CaseNumber, c);
        }
        for (Request r : requests) {
            Response resp = new Response();
            Case c = byNumber.get(r.caseNumber);
            if (c != null) {
                resp.status = c.Status;
                resp.priority = c.Priority;
                resp.lastModified = c.LastModifiedDate;
            } else {
                resp.status = 'Not found';
            }
            out.add(resp);
        }
        return out;
    }
}
