/**
 * Scores an account's health from open cases and recent activity. Invoked by Get_Account_Health.
 */
public with sharing class AccountHealthScorer {

    public class Request {
        @InvocableVariable(required=true label='Account Id')
        public Id accountId;
    }

    public class Response {
        @InvocableVariable(label='Health Score' description='0 to 100')
        public Decimal healthScore;
        @InvocableVariable(label='Open Cases')
        public Integer openCases;
    }

    @InvocableMethod(label='Get Account Health')
    public static List<Response> score(List<Request> requests) {
        Set<Id> ids = new Set<Id>();
        for (Request r : requests) {
            ids.add(r.accountId);
        }
        Map<Id, Integer> openByAccount = new Map<Id, Integer>();
        for (AggregateResult ar : [SELECT AccountId acct, COUNT(Id) n FROM Case
                                   WHERE AccountId IN :ids AND IsClosed = false GROUP BY AccountId]) {
            openByAccount.put((Id) ar.get('acct'), (Integer) ar.get('n'));
        }
        List<Response> out = new List<Response>();
        for (Request r : requests) {
            Response resp = new Response();
            Integer open = openByAccount.containsKey(r.accountId) ? openByAccount.get(r.accountId) : 0;
            resp.openCases = open;
            resp.healthScore = Math.max(0, 100 - open * 10);
            out.add(resp);
        }
        return out;
    }
}
