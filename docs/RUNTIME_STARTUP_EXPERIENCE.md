# Runtime startup experience

Mission Control shows staged startup:

1. Starting runtime  
2. Loading workers  
3. Loading operational memory  
4. Loading governance timeline  
5. Loading runtime intelligence  
6. Runtime ready  

APIs: `/api/v1/runtime/startup`, `/readiness`, `/hydration/stages`, `/bootstrap`.

Heavy hydration uses cached/partial truth; degraded responses instead of hanging.
