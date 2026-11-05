from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from web import services
from web.forms import TaskForm
from web.models import Task

TEST_NAMES = {
    "mannwhitney": "Манна—Уитни",
    "ttest": "t-критерий",
    "permutation": "Перестановочный",
}


@login_required
def task_list(request):
    tasks = Task.objects.filter(owner=request.user)[:50]
    return render(request, "web/list.html", {"tasks": tasks})


@login_required
def task_create(request):
    form = TaskForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            rows = services.parse_csv_file(
                form.cleaned_data["file"], form.cleaned_data["text_col"], form.cleaned_data["group_col"]
            )
            params = {
                "rows": rows,
                "test": form.cleaned_data["test"],
                "top_n": form.cleaned_data["top_n"],
                "n_permutations": form.cleaned_data["n_permutations"],
                "seed": form.cleaned_data["seed"],
            }
            owner = request.user  # @login_required гарантирует, что сюда анонимный пользователь не попадёт
            task = services.create_task(form.cleaned_data["name"], params, owner=owner)
            return redirect("task_detail", pk=task.pk)
        except ValueError as exc:
            form.add_error("file", str(exc))
    return render(request, "web/form.html", {"form": form})


@login_required
def task_detail(request, pk: int):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    context = {"task": task, "test_name": TEST_NAMES.get(task.params.get("test"), task.params.get("test"))}
    if task.result:
        pvalue = task.result.get("pvalue")
        context["test_result_name"] = TEST_NAMES.get(task.result.get("test"), task.result.get("test"))
        if pvalue is not None:
            context["pvalue_percent"] = pvalue * 100
            context["differ"] = pvalue < 0.05
    return render(request, "web/detail.html", context)
