/**
 * Merges duplicate contacts into a primary. Invoked by Merge_Duplicate_Contacts.
 * The primary is passed as a full Contact record, which no schema type can describe.
 */
public with sharing class ContactMerger {

    public class Request {
        @InvocableVariable(required=true label='Primary Contact')
        public Contact primary;
        @InvocableVariable(label='Duplicate Ids')
        public List<Id> duplicateIds;
    }

    public class Response {
        @InvocableVariable(label='Merged Id')
        public Id mergedId;
    }

    @InvocableMethod(label='Merge Duplicate Contacts')
    public static List<Response> mergeAll(List<Request> requests) {
        List<Response> out = new List<Response>();
        for (Request r : requests) {
            Response resp = new Response();
            if (r.duplicateIds != null && !r.duplicateIds.isEmpty()) {
                List<Contact> dupes = [SELECT Id FROM Contact WHERE Id IN :r.duplicateIds];
                merge r.primary dupes;
            }
            resp.mergedId = r.primary.Id;
            out.add(resp);
        }
        return out;
    }
}
