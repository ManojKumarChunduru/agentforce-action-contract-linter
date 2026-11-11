/**
 * Returns a summary of an account's recent orders. Invoked by the Get_Order_History action.
 */
public with sharing class OrderHistoryService {

    public class Request {
        @InvocableVariable(required=true label='Account Id')
        public Id accountId;
        @InvocableVariable(label='Months Back' description='How many months of history to include')
        public Integer monthsBack;
    }

    public class Response {
        @InvocableVariable(label='Order Summaries')
        public List<String> orderSummaries;
        @InvocableVariable(label='Total Orders')
        public Integer totalOrders;
    }

    @InvocableMethod(label='Get Order History')
    public static List<Response> history(List<Request> requests) {
        Set<Id> accountIds = new Set<Id>();
        for (Request r : requests) {
            accountIds.add(r.accountId);
        }
        Map<Id, List<Order>> byAccount = new Map<Id, List<Order>>();
        for (Order o : [SELECT Id, AccountId, OrderNumber, Status, TotalAmount
                        FROM Order WHERE AccountId IN :accountIds ORDER BY CreatedDate DESC]) {
            if (!byAccount.containsKey(o.AccountId)) {
                byAccount.put(o.AccountId, new List<Order>());
            }
            byAccount.get(o.AccountId).add(o);
        }
        List<Response> out = new List<Response>();
        for (Request r : requests) {
            Response resp = new Response();
            resp.orderSummaries = new List<String>();
            List<Order> orders = byAccount.get(r.accountId);
            if (orders != null) {
                for (Order o : orders) {
                    resp.orderSummaries.add(o.OrderNumber + ': ' + o.Status);
                }
            }
            resp.totalOrders = resp.orderSummaries.size();
            out.add(resp);
        }
        return out;
    }
}
