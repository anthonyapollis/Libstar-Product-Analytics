define([], function () {
  return {
    type: "items",
    component: "accordion",
    items: {
      dimensions: { uses: "dimensions", min: 0, max: 0 },
      measures: { uses: "measures", min: 0, max: 0 },
      sorting: { uses: "sorting" },
      settings: {
        uses: "settings",
        items: {
          page: {
            ref: "defaultPage",
            label: "Dashboard page",
            type: "string",
            component: "dropdown",
            defaultValue: "exec",
            options: [
              { value: "exec", label: "Executive Command Centre" },
              { value: "portfolio", label: "Category & Brand Portfolio" },
              { value: "network", label: "Channel & Regional Network" },
              { value: "quality", label: "Data Quality Control" },
              { value: "ml", label: "ML Decision Lab" },
              { value: "explorer", label: "Product Exception Explorer" }
            ]
          }
        }
      }
    }
  };
});
