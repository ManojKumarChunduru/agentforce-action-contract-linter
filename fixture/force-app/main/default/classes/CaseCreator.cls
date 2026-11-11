/**
 * Creates a case on behalf of a contact. Invoked by the Create_Case agent action.
 * Bulk-safe: one insert for every request in the list.
 */
public with sharing class CaseCreator {

    public class Request {
        @InvocableVariable(required=true label='Subject')
        public String subject;
        @InvocableVariable(required=true label='Description')
        public String description;
        @InvocableVariable(required=true label='Contact Id' description='The contact the case is for')
        public Id contactId;
        @InvocableVariable(label='Priority' description='Low, Medium or High; defaults to Medium')
        public String priority;
    }

    public class Response {
        @InvocableVariable(label='Case Id')
        public Id caseId;
        @InvocableVariable(label='Case Number')
        public String caseNumber;
    }

    @InvocableMethod(label='Create Case' description='Create a case for a contact')
    public static List<Response> create(List<Request> requests) {
        List<Case> cases = new List<Case>();
        for (Request r : requests) {
            cases.add(new Case(
                Subject = r.subject,
                Description = r.description,
                ContactId = r.contactId,
                Priority = String.isBlank(r.priority) ? 'Medium' : r.priority
            ));
        }
        insert cases;
        List<Response> out = new List<Response>();
        for (Case c : [SELECT Id, CaseNumber FROM Case WHERE Id IN :cases]) {
            Response resp = new Response();
            resp.caseId = c.Id;
            resp.caseNumber = c.CaseNumber;
            out.add(resp);
        }
        return out;
    }
}
