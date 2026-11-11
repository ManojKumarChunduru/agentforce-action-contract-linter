/**
 * Drafts a customer reply for a case in a requested tone. Invoked by Draft_Customer_Reply.
 */
public with sharing class ReplyDrafter {

    public class Request {
        @InvocableVariable(required=true label='Case Id')
        public Id caseId;
        @InvocableVariable(label='Tone' description='Formal, Friendly or Brief')
        public String tone;
        @InvocableVariable(label='Extra Context')
        public String extraContext;
    }

    public class Response {
        @InvocableVariable(label='Draft')
        public String draft;
    }

    @InvocableMethod(label='Draft Customer Reply')
    public static List<Response> draft(List<Request> requests) {
        List<Response> out = new List<Response>();
        for (Request r : requests) {
            Response resp = new Response();
            String tone = String.isBlank(r.tone) ? 'Friendly' : r.tone;
            resp.draft = '[' + tone + '] Thank you for contacting us about your case.';
            out.add(resp);
        }
        return out;
    }
}
