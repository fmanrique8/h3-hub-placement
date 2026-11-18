# Bibliography

## Location and aggregation

- Goodchild, Michael F. (1979). [The Aggregation Problem in Location-Allocation](https://doi.org/10.1111/j.1538-4632.1979.tb00692.x). *Geographical Analysis*. The foundational motivation for assessing how discarded spatial detail can change a site decision.
- Qi, Lian, and Zuo-Jun Max Shen (2010). [Worst-case analysis of demand point aggregation for the Euclidean p-median problem](https://www.sciencedirect.com/science/article/abs/pii/S0377221709003531). *European Journal of Operational Research*. Relevant to the geometry of the point-to-representative distance term and to deliberately difficult input designs.
- Irawan, Chandra Ade, Said Salhi, and Maria Paola Scaparra. [An Adaptive Multiphase Approach for Large Unconditional and Conditional p-Median Problems](https://kar.kent.ac.uk/38849/1/EJOR%28Chandra-Said-Paola-2014%29.pdf). *European Journal of Operational Research*. See section 1 for the discrete model and the abstract for post-optimization on original demands. The present comparison keeps candidate sites and solver settings fixed.
- Cebecauer, Matej, and Ľuboš Buzna (2017). [A Versatile Adaptive Aggregation Framework for Spatially Large Discrete Location-Allocation Problems](https://doi.org/10.1016/j.cie.2017.07.022). *Computers & Industrial Engineering*. [Author manuscript](https://frdsa.fri.uniza.sk/~buzna/page2/paperCIE.pdf). Direct precedent for adapting the aggregation to the structure of location-allocation inputs.

## Implementations

- Uber Engineering (2018). [H3: Uber’s Hexagonal Hierarchical Spatial Index](https://www.uber.com/us/en/blog/h3/). [Hierarchical grid functions](https://h3geo.org/docs/api/hierarchy/) and [logical and geographic containment](https://h3geo.org/docs/highlights/indexing/). These inform the boundaries and exact parent roll-up used by h3-py 4.3.1.
- SciPy 1.15.3. [Mixed-integer linear programming](https://docs.scipy.org/doc/scipy-1.15.3/reference/generated/scipy.optimize.milp.html). Solver statuses, the reported relative MIP gap, and the HiGHS interface. [HiGHS documentation](https://highs.dev/).
- scikit-learn 1.6.1. [K-means](https://scikit-learn.org/1.6/modules/generated/sklearn.cluster.KMeans.html). Sample weights and the fixed multistart settings for the non-H3 baseline.

## Data and postal references

- Manrique, Felipe. [Synthetic fixture generator `synthetic-v1`](hub_placement/fixtures.py) and [recorded data and version notes](DATA.md). The original point and candidate fixtures are the experiment's only data source.
- HUD. [HUD–USPS ZIP Code Crosswalk Files](https://www.huduser.gov/portal/datasets/usps_crosswalk.html). ZIP-to-tract mapping direction, address denominators, and vintage notes for the documented optional import.
- U.S. Census Bureau. [2024 Gazetteer Files](https://www.census.gov/geographies/reference-files/2024/geo/gazetter-file.html) and [ZIP Code Tabulation Areas](https://www.census.gov/programs-surveys/geography/guidance/geo-areas/zctas.html). Representative coordinates for Census geographies and the ZIP versus ZCTA distinction. These are references for follow-up work.
- U.S. Census Bureau. [TIGERweb January 2020 Census Blocks, layer 10](https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/10). Internal-point latitude and longitude, block IDs, and population used in the separate Madison follow-up.
- U.S. Census Bureau. [2024 TIGER/Line All Lines archive, Dane County](https://www2.census.gov/geo/tiger/TIGER2024/EDGES/tl_2024_55025_edges.zip) and [2024 TIGER/Line technical documentation](https://www2.census.gov/geo/pdfs/maps-data/data/tiger/tgrshp2024/TGRSHP2024_TechDoc.pdf). Edge geometry, topological endpoint IDs, and MAF/TIGER roadway classes used to build the modeled road network.
