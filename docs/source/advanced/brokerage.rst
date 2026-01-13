====================================
Brokerage
====================================

The brokerage is one of the most crucial functions in the system to distribute workload among computing resources.
It has the following goals:

* To assign enough jobs to computing resources to utilize all available CPUs continuously.

* To minimize the waiting time for each job to produce output data.

* To execute jobs in such a way that the jobs respect their priorities and resource allocations.

* To choose computing resources for each job based on characteristics of the job and constraints of the computing resources.

It is not straightforward to satisfy those goals for all jobs since some of them are logically contradictory.
The brokerage has a plugin structure so that organizations can provide their algorithms according to
their needs and use-cases.

This page explains the algorithms of some advanced plugins.

|br|

.. contents:: Table of Contents
    :local:
    :depth: 2

------------

|br|

ATLAS Production Task Brokerage
-------------------------------------
The ATLAS production task brokerage assigns each task to a nucleus as follows:

#. Generate the primary list of nuclei in the ACTIVE status.

#. Filter out the list with the following checks:

   * Nuclei are skipped if there are long transfer backlogs unless ``t1Weight`` of the task is negative.

   * Nuclei must have associated storages.

   * The storages associated to nuclei must have enough space:

     .. math::

        spaceFree + spaceExpired - normalizedExpOutSize \times RW > diskThreshold

     where *spaceFree* is the free space size in the associated storage, *spaceExpired* is the size of the space
     that expired secondary data occupies, *normalizedExpOutSize* is the expected size of the output file normalized
     by cpuTime :raw-html:`&times;` corePower :raw-html:`&times;` day (0.25), *RW* is the total amount
     of exiting workload assigned to the nucleus. *diskThreshold* is the threshold defined per gshare
     as ``DISK_THRESHOLD_<gshare>`` in :doc:`gdpconfig </advanced/gdpconfig>`. If not specified per gshare,
     ``DISK_THRESHOLD`` defines it for all, with a default value of 100 TB.

   * The storages associated to nuclei must be able to send input files to satellites and receive output files
     from sattellites over WAN, i.e., their ``read_wan`` and ``write_wan`` must be ``ON``.

   * Nuclei must pass the data locality check with the following rules:

      * All input datasets are considered if the ``taskBrokerOnMaster`` task parameter is set to False or is
        unspecified. Otherwise, only the primary input dataset is considered, i.e., secondary datasets are ignored.

      * Nuclei with incomplete local data can be used if the ``inputPreStaging`` task parameter is set to
        True since the parameter enables the data carousel mode and guarantees the input data completeness.
        Those nuclei ignore the next two rules with the input data size and the number of input files.

      * The fraction of the data size locally available divide by the total input size must be larger than
        ``INPUT_SIZE_FRACTION`` (defined in :doc:`gdpconfig </advanced/gdpconfig>`) if the total input size is
        larger than ``INPUT_SIZE_THRESHOLD`` (defined in :doc:`gdpconfig </advanced/gdpconfig>`).

      * The fraction of the number of files locally available divide by the total number of input files must be larger
        than ``INPUT_NUM_FRACTION`` (defined in :doc:`gdpconfig </advanced/gdpconfig>`) if the total input size is
        larger than ``INPUT_NUM_THRESHOLD`` (defined in :doc:`gdpconfig </advanced/gdpconfig>`).
　　　　
      * The entire data locality check is disabled if no nuclei pass and

         * ``ioIntencity`` of the task is less than or equal to ``MIN_IO_INTENSITY_WITH_LOCAL_DATA`` and
           the total input size is less than or equal to ``MIN_INPUT_SIZE_WITH_LOCAL_DATA``, or

         * ``taskPriority`` of the task is larger than or equal to ``MAX_TASK_PRIO_WITH_LOCAL_DATA``.

        ``MIN_blah`` and ``MAX_blah`` are defined in :doc:`gdpconfig </advanced/gdpconfig>`.

#. Calculate brokerage weight for remaining nuclei using the following formula to choose a nuclei based on that:

   When ``ioIntencity`` of the task is greater than ``MIN_IO_INTENSITY_WITH_LOCAL_DATA``

   .. math::

     weight =\frac {localInputSize \times tapeWeight \times (spaceFree + spaceExpired) \times min(spaceFreeCutoff, spaceFree)} {max(rwOffset, RW) \times totalInputSize \times spaceTotal}

   Otherwise,

   .. math::

     weight =\frac {tapeWeight \times (spaceFree + spaceExpired) \times min(spaceFreeCutoff, spaceFree)} {max(rwOffset, RW) \times spaceTotal}


   where *localInputSize* is the size of input data locally available, *totalInputSize* is the total size of
   input data, *tapeWeight* is 0.001 if input data is on the tape storage, or 1 otherwise, *rwOffset* is 50 to have
   the minimum offset for *RW*, *spaceFreeCutoff* is the maximum free disk space value that will be factored into
   the calculation (``FREE_DISK_CUTOFF`` in :doc:`gdpconfig </advanced/gdpconfig>`), and *spaceTotal* is the total size of the storage.

#. If all nuclei are skipped, the task is pending for 30 min and then gets retried.

------------


|br|

ATLAS Production Job Brokerage
-------------------------------------

Here is the ATLAS production job brokerage flow:

#. Generate the list of preliminary candidates from one of the following:

   * All queues while excluding any queue with case-insensitive 'test' in the name.

   * A list of pre-assigned queues. Unified queues are resolved to pseudo-queues. Although merge jobs are pre-assigned
     to avoid transferring small pre-merged files, the pre-assignment is ignored if the relevant queues have been skipped
     for 24 hours.

#. Filter out preliminary candidates that don't pass any of the following checks:

   * The queue status must be *online* unless the queues are pre-assigned.

   * Skip queues if their links to the nucleus are blocked.

   * Skip queues if over the ``NQUEUED_SAT_CAP`` (defined in :doc:`gdpconfig </advanced/gdpconfig>`) files queued
     on their links to the nucleus.

   * Skip all queues if the number of files to be aggregated to the nucleus is larger than ``NQUEUED_NUC_CAP_FOR_JOBS``
     (defined in :doc:`gdpconfig </advanced/gdpconfig>`).

   * If priority :raw-html:`&GreaterEqual;` 800 or scout jobs or merging jobs or pre-merged jobs, skip inactive queues
     (where no jobs got started in the last 2 hours although activated jobs had been there).

   * If priority :raw-html:`&GreaterEqual;` 800 or scout jobs, skip opportunistic queues
     (defined as queues with ``pledgedcpu=-1``).

   * Zero Share, which is defined in the ``fairsharepolicy`` field in CRIC. For example *type=evgen:100%,type=simul:100%,type=any:0%*,
     in this case, only evgen or simul jobs can be assigned as others have zero shares. See a more detailed description further below in this page.

   * If the task ``ioIntensity`` is larger than ``IO_INTENSITY_CUTOFF`` (defined in :doc:`gdpconfig </advanced/gdpconfig>`),
     the total size of missing files must be less than ``SIZE_CUTOFF_TO_MOVE_INPUT`` (defined in :doc:`gdpconfig </advanced/gdpconfig>`)
     and the number of missing files must be less than ``NUM_CUTOFF_TO_MOVE_INPUT`` (defined in :doc:`gdpconfig </advanced/gdpconfig>`).
     I.e., if a queue needs to transfer more input files, the queue is skipped.

   * There is a general ``MAX_DISKIO_DEFAULT`` limit in :doc:`gdpconfig </advanced/gdpconfig>`.
     It is possible to overwrite the limit for a particular queue through the ``maxDiskIO`` (in kB/sec per core)
     field in CRIC. The limit is applied in job brokerage: when the average diskIO per core for running jobs in
     a queue exceeds the limit, the next cycles of job brokerage will exclude tasks with ``diskIO`` higher than
     the defined limit to progressively get the diskIO under the threshold.

   * CPU Core count matching amount site.coreCount, task.coreCount, and maxCoreCount of the task if defined.

   * Availability of ATLAS release/cache. This check is skipped when queues have *ANY* in the ``releases`` filed in CRIC.
     If queues have *AUTO* in the ``releases`` filed, the brokerage uses the information published in a json by CRIC as
     explained at :ref:`this section <ref_auto_check>`.

   * Queues publish maximum (and minimum) memory size per core. The expected memory site of each job is estimated
     for each queue as

     .. math::

        (baseRamCount + ramCount \times coreCount) \times compensation

     where *compensation* is 0.9, avoiding sending jobs to high-memory queues when their expected memory usage is
     close to the lower limit. Queues are skipped if the estimated memory usage is not included in the acceptable
     memory ranges.

   * Skip queues if they don't support direct access to read input files from the local storage, although the task is
     configured to use only direct access.

   * The disk usage for a job is estimated as

     .. math::

        inputDiskCount + max (1.5 GB, outDiskCount \times nEvents \: or \: outDiskCount \times inputDiskCount) + max (300 MB, workDiskCount)

     *inputDiskCount* is the total size of job input files, a discrete function of *nEvents*.
     *nEvents* is the smallest number of events in a single job allowed based on the task requirements and is used to estimate the output size
     by multiplying *outDiskCount* when *outDiskCountUnit* ends with "PerEvents", otherwise, *inputDiskCount* is used.
     *inputDiskCount* is zero
     if the queues are configured to read input files directly from the local storage. ``maxwdir`` is divided by
     *coreCount* at each queue and the resultant value must be larger than the expected disk usage.

   * DISK size check, free space in the local storage has to be over 200GB.

   * Skip queues if their storage endpoints are blacklisted:

     * For all queues.

       * Input endpoints must be locally readable over LAN (``read_lan`` = ``ON``).

       * Output endpoints must be locally writable over LAN (``write_lan`` = ``ON``).

     * For sattelite queues in addition:

       * Input endpoints must be able to receive files over WAN (``write_wan`` = ``ON``).

       * Output endpoints must be able to send files over WAN (``read_wan`` = ``ON``).

       * The nucleus storage endpoints must allow receivng and sending files over WAN (``write_wan`` = ``ON`` and ``read_wan`` = ``ON``).

   * If scout or merge jobs, skip queues if their ``maxtime`` is less than 24 hours.

   * The estimated walltime for a job is

     .. math::

        \frac {cpuTime \times nEvents} {C \times P \times cpuEfficiency} + baseTime

     *nEvents* is the same as the one used to estimate the disk usage. The estimated walltime must be between ``mintime`` and ``maxtime`` at the queue.

   * ``wnconnectivity`` of the queue must be consistent if the task specifies ``ipConnectivity``.
     The format of ``wnconnectivity`` and ``ipConnectivity`` is ``network_connectivity#ip_stack``.
     *network_connectivity* of the queue is

      * full: to accept any tasks since outbound network connectivity is fully available,

      * http: to accept tasks with *network_connectivity=http* or *none* since only http access is available, or

      * none: to accept tasks with *network_connectivity=none* since no outbound network connectivity is available,

     *ip_stack* of the queue is

      * IPv4: to accept tasks with *ip_stack=IPv4*,

      * IPv6: to accept tasks with *ip_stack=IPv6*, or

      * '' (unset): to accept tasks without specifying *ip_stack*.

   * Settings for event service and the dynamic number of events.

   * Too many transferring jobs: skip if transferring > max(transferring_limit, 2 x running), where transferring_limit limit is defined by site or 2000 if undefined.

   * Use only the queues associated with the nucleus if the task sets ``t1Weight=-1`` and normal jobs are being generated.

   * Skip queues without pilots for the last 3 hours.

   * If processingType=*urgent* or priority :raw-html:`&GreaterEqual;` 1000, the :ref:`Network weight <ref_network_weight>`
     must be larger than or equal to ``NW_THRESHOLD`` :raw-html:`&times;` ``NW_WEIGHT_MULTIPLIER``
     (both defined in :doc:`gdpconfig </advanced/gdpconfig>`).

   * When ``WORK_SHORTAGE`` in :doc:`gdpconfig </advanced/gdpconfig>` is set to True, the following queues are skipped:

      * Opportunistic queues defined with ``pledgedcpu=-1``.

      * Partially pledged queues defined with positive ``pledgedcpu`` when the total number of running cores is larger than ``pledgedcpu``.

#. Calculate brokerage weight for remaining candidates.
   The initial weight is based on running vs queued jobs.
   The brokerage uses the largest one as the number of running jobs among the following numbers:

   * The actual number of running jobs at the queue, *R*\ :sub:`real`.

   * min(*nBatchJob*, 20) if *R*\ :sub:`real` < 20 and *nBatchJob* (the number of running+submitted
     batch workers at PQ) > *R*\ :sub:`real`. Mainly for bootstrap.

   * *numSlots* if it is set to a positive number for the queue to the `proactive job assignment <https://github.com/HSF/harvester/wiki/Workflows#proactive-job-assignment>`_.

   * The number of starting jobs if *numSlots* is set to zero, which is typically useful for Harvester to fetch
     jobs when the number of available slots dynamically changes.

   The number of assigned jobs is ignored for the weight calculation and the subsequent filtering if the input for
   the jobs being considered is already
   available locally. Jobs waiting for data transfer do not block new jobs needing no transfer.

   .. math::

     manyAssigned = max(1, min(2, \frac {assigned} {activated}))

   .. math::

     weight = \frac {running + 1} {(activated + assigned + starting + defined + 10) \times manyAssigned}

   Take data availability into consideration.

   .. math::

     weight = weight \times \frac {availableSize + totalSize} {totalSize \times (numMissingFiles / 100 + 1)}

   Apply a :ref:`Network weight <ref_network_weight>` based on connectivity between nucleus and satellite,
   since the output files are aggregated to the nucleus.

   .. math::

     weight = weight \times networkWeight

#. Apply further filters.

   * Skip queues if activated + starting > 2 :raw-html:`&times;` running.

   * Skip queues if defined+activated+assigned+starting > 2 :raw-html:`&times;` running.

#. If all queues are skipped, the task is pending for 1 hour.
   Otherwise, the remaining candidates are sorted by weight, and the best 10 candidates are taken.

|br|

.. _ref_auto_check:

Release/cache Availability Check for releases=AUTO
=========================================================
Each queue publishes something like

.. code-block:: python

  "AGLT2": {
    "cmtconfigs": [
      "x86_64-centos7-gcc62-opt",
      "x86_64-centos7-gcc8-opt",
      "x86_64-slc6-gcc49-opt",
      "x86_64-slc6-gcc62-opt",
      "x86_64-slc6-gcc8-opt"
    ],
    "containers": [
      "any",
      "/cvmfs"
    ],
    "cvmfs": [
      "atlas",
      "nightlies"
    ],
    "architectures": [
      {
        "arch": ["x86_64"],
        "instr": ["avx2"],
        "type": "cpu",
        "vendor": ["intel","excl"]
      },
      {
        "type": "gpu",
        "vendor": ["nvidia","excl"],
        "model":["kt100"],
        "version": "11.0.3",
      }
    ],
    "tags": [
      {
        "cmtconfig": "x86_64-slc6-gcc62-opt",
        "container_name": "",
        "project": "AthDerivation",
        "release": "21.2.2.0",
        "sources": [],
        "tag": "VO-atlas-AthDerivation-21.2.2.0-x86_64-slc6-gcc62-opt"
      },
      {
        "cmtconfig": "x86_64-slc6-gcc62-opt",
        "container_name": "",
        "project": "Athena",
        "release": "21.0.38",
        "sources": [],
        "tag": "VO-atlas-Athena-21.0.38-x86_64-slc6-gcc62-opt"
      }
    ]
  }


Checks for CPU and/or GPU Hardware
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The old format of task ``architecture`` is ``sw_platform<@base_platform><#host_cpu_spec><&host_gpu_spec>`` where
``host_cpu_spec`` is ``architecture<-vendor<-instruction_set>>`` and
``host_gpu_spec`` is ``vendor<-model>``.
It is possible to use regexp in the ``architecture`` field of ``host_cpu_spec`` like "(x86_64|aarch64)" to be matched
with x86_64 or aarch64 queues.
If ``#host_cpu_spec`` is not specified in task's ``architecture``, the first part of ``sw_platform`` is used as
CPU architecture.
The regexp in ``sw_platform`` is resolved to a relevant string in the ``cmtconfigs`` list of the queue.

The new format of task ``architecture`` is a JSON-serialized dictionary with the following keys: ``sw_platform``, ``base_platform``,
``cpu_specs``, and ``gpu_spec``.
The ``cpu_specs`` is a list of dictionaries with the following keys: ``arch``, ``instr``, ``type``, and ``vendor``.
The ``gpu_spec`` is a dictionary with the keys ``vendor``, ``model``, and ``version``, where ``version`` is a optional string composed of
``comparison_operator`` (==, >=, <=, >, <, !=) and ``version_value`` (e.g., ``>=11.0``).

If ``host_cpu_spec`` or ``host_gpu_spec`` is specified, the brokerage checks the ``architectures`` of the queue (shown in the above example).
The ``architectures`` can contain two dictionaries to describe CPU and GPU hardware specifications at the queue.
All attributes of the
dictionaries except for the *type* attribute take lists of strings. If 'attribute': ['blah'], the queue
accepts tasks with attribute='blah' or without specifying the attribute. If 'excl' is included in the list,
the queue accepts only tasks with attribute='blah'.
For example, tasks with *#x86_64* are accepted by queues with "arch": ["x86_64"], "arch": [""],
or "arch": ["x86_64", "excl"], but not by "arch": ["arm64"].
If the ``version`` of ``gpu_spec`` is specified, the queue's GPU hardware specification must have the ``version`` attribute and
its value must be either ``any`` or a version string matching with the specified ``version`` and comparison operator.


Checks for Fat Containers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If the task uses a container, i.e., the ``container_name`` attribute is set, the brokerage checks as follows:

* If the task uses only tags, i.e., it sets ``onlyTagsForFC``, the ``container_name`` must be equal to
  the *container_name* of a tag in the ``tags`` list or must be included in the ``sources`` of a tag in
  the ``tags`` list.

* If the task doesn't set ``onlyTagsForFC``,

   * 'any' or '/cvmfs' must be included in the ``containers`` list, or

   * ``container_name`` must be forward-matched with one of the strings in the ``containers`` list, or

   * ``container_name`` is resolved to the source path using the dictionary of the "ALL" queue, and
     the resolved source path must be forward-matched with one of the strings in the ``containers`` list.

Note that ``@base_platform`` may include the container image name of the base platform, formatted as
``@base_platform_name+base_container_image``. This string is provided to the pilot for configuring the
container environment before executing the payload, but it is not utilized by the brokerage.

Checks for Releases, Caches, or Nightlies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Checks are as follows for releases, caches, and nightlies:

* 'any' or *cvmfs_tag* must be included in the ``cvmfs`` list, where *cvmfs_tag* is *atlas* for
  standard releases and caches or *nightlies* for nightlies. In addition,

   * 'any' or '/cvmfs' must be included in the ``containers`` list, or

   * the task ``sw_platform`` is extracted from the task ``architecture`` and must be included in the ``cmtconfigs`` list.

* If the above is not the case,

   * 'any' must be in the ``containers`` list or ``base_platform`` in the task ``architecture`` must be empty, and

   * the task ``sw_platform``, ``sw_project``, and ``sw_version`` must be equal to ``cmtconfig``, ``project``, and
     ``release`` of a tag in the ``tags`` list.

|br|

.. _ref_network_weight:

Network Weight
==========================
The network data sources are

* the `Network Weather Service <http://atlas-adc-netmetrics-lb.cern.ch/metrics/latest.json>`_ as the dynamic source, and

* the `CRIC closeness <https://atlas-cric.cern.ch/api/core/sitematrix/query/?json&json_pretty=0>`_ as a semi static source.

Given the accuracy of the data and the timelapse from decision to action, the network weight only aims to provide
a simple, dynamic classification of links. It is currently calculated as:

.. math::

  netWorkWeight = 0.5 \times (queuedWeight + throughputWeight)

where the queued and throughput weight are calculated as in the plot below:

.. figure:: images/queued.png
  :align: center

  queuedWeight

.. figure:: images/throughput.png
  :align: center

  throughputWeight

It uses the most recent available data, so preferably data of the last 1 hour, if not available of last 1 day,
if not available of last 1 week. FTS Mbps are used, which are filled from Chicago elastic search.
If there are no available network metrics, the AGIS closeness (0 best to 11 worst) is used in a normalized way

.. math::

  weightNwThroughput = 1+ \frac {MAX\_CLOSENESS - closeness} {MAX\_CLOSENESS - MIN\_CLOSENESS}

|br|

Timeout Rules
==============

* 1 hour for pending jobs
* 4 hours for defined jobs
* 12 hours for assigned jobs
* 7 days for throttled jobs
* 2 days for activated or starting jobs
* 4 hours for activated or starting jobs with job.currentPriority>=800 at the queues where ``laststart`` in the
  ``SiteData`` table is older than 2 hours or the queue status is test or offline
* 30 min for sent jobs
* 21 days for running jobs
* 2 hours for heartbeats from running or starting jobs. Each ``workflow`` can define own timeout value using
  :hblue:`HEARTBEAT_TIMEOUT_<workflow>` in :doc:`gdpconfig </advanced/gdpconfig>`
* the above :hblue:`HEARTBEAT_TIMEOUT_<workflow>` for transferring jobs with the ``workflow`` and own stage-out
  mechanism that sets not-null job.jobSubStatus
* 3 hours for holding jobs with job.currentPriority>=800, while days for holding jobs with job.currentPriority<800
* ``transtimehi`` days for transferring jobs with job.currentPriority>=800, while
  ``transtimelo`` days for transferring jobs with job.currentPriority<800
* disable all timeout rules when the queue status is :green:`paused` or the queue has :green:`disableReassign`
  in ``catchall``
* fast rebrokerage for defined, assigned, activated, or starting jobs at the queues
  where
   * nQueue_queue(gshare)/nRun_queue(gshare) is larger than :hblue:`FAST_REBRO_THRESHOLD_NQNR_RATIO`
   * nQueue_queue(gshare)/nQueue_total(gshare) is larger than :hblue:`FAST_REBRO_THRESHOLD_NQUEUE_FRAC`
   * nQueue_queue(gshare) is larger than :hblue:`FAST_REBRO_THRESHOLD_NQUEUE_<gshare>`. Unless the gshare
     defines the parameter it doesn't trigger the fast rebrokerage
   * :hblue:`FAST_REBRO_THRESHOLD_blah` is defined in :doc:`gdpconfig </advanced/gdpconfig>`
   * nSlots is not defined in the ``Harvester_Slots`` table since it intentionally cause large nQueue
     when nRun is small

Zero Share (or FairSharePolicy in CRIC)
==============
The Zero Share filter looks for reasons to exclude jobs from a site ("site X has zero share for this activity"). Despite having shares in the name, the
current implementation simply accepts or rejects jobs based on the site's policy.

The syntax of the `fairsharepolicy` field in
CRIC is a concatenation of subpolicies: `<subpolicy1>,<subpolicy2>,<subpolicy3>,...` Unwanted spaces can break the matching of the policies. Brokerage will run through the subpolicies and end *at the first one* that applies
either positively or negatively.

Each subpolicy has the format: `<key><filter>:<value>`

Where KEY is one of: `priority`, `type`, `group`, `gshare`.

* `Priority` refers to the task `currentPriority`. In the FILTER you can use any comparison operator (`>`, `<`, `>=`, `<=`, `==`, `!=`) and the priority
  threshold you need. Note that some jobs with unwanted priority can still slip through: job priority can increase while queued, or scouts are generated
  with a different priority than the task. The priority check can be skipped, which is currently done for merge jobs.

* `Type` refers to the task `processingType`. The valid types are defined as: `evgen`, `simul`, `reprocessing`, `test`, `group`, `deriv`, `pile`, `merge`.
  Note that `test` resolves to the types `prod_test`, `validation`, `ptest`, `rc_test`, `rc_test2`, `rc_alrb`.

* `Group` refers to the task `workingGroup` (AP_Higgs, AP_Susy, Higgs...). There is no restriction on the groups that can be used.

* `Gshare` refers to the task `gshare` as defined in the global shares table. There is no restriction on the global shares that can be used.

For type, group and gshare, you can use the wildcard `*` and other regular expressions.

The VALUE is expressed as a percentage with or without the `%` sign (e.g. `type=evgen:100%` or `type=evgen:100` is exactly the same). While the original purpose of the value
was to express the share of the site for the given type, it is not used in the current implementation. Note that the value, except for `0`, does
not make a difference, so it's recommended to just use `0` or `100`.

Let's look at some expected and unexpected examples:

* `type=evgen:100%,type=simul:100%,type=any:0%` means that the site accepts `evgen` and `simul`, but has zero share for anything else.
* `priority>500:0,type=simul:100%,type=any:0%` means the site will reject tasks with currentPriority above 500, will accept `simul` tasks and reject anything else.
* `type=evgen:100%,type=simul:100%` means that the site accepts `evgen` and `simul`, but is not rejecting other types, so anything will run on this site.
* `type=evgen:100%,type=simul:100%,type=any:0%,priority>500:0%` means that the site accepts `evgen` and `simul`, rejects any other types and -supposedly- will
  also reject tasks with `currentPriority` above `500`. However given the order of the subpolicies, the priority filter will not be applied if the task is
  `evgen` or `simul`, so you could be getting higher priority tasks assigned!
* Be careful with combinations between keys. They are allowed, but not always predictable. For example
  `type=evgen:100%,type=any:0%,gshare=Express:100%,gshare=any:100%` will iterate through the subpolicies, accept `evgen` tasks, reject other types and
  should not even get to the `gshare` subpolicies.
* Reordering the previous policy to `type=evgen:100%,gshare=Express:100%,type=any:0%,gshare=any:100%` will accept tasks with `processingType=evgen` or
  `gshare=Express` and reject everything else.
* On the usage of regular expressions, you could use `gshare=Express*:100%,gshare=any:100%` if you want to map the same subpolicy for
  `Express` and `Express Analysis`.
* Another useful regular expression could be `group=(AP_Higgs|AP_Susy|AP_Exotics|Higgs):0%` to accept a list of groups.

------------

|br|

Special Brokerage for ATLAS Full-chain
------------------------------------------------
There is a mechanism in the ATLAS production task and job brokerages to assign an entire workflow (full-chain)
to a specific nucleus.
The main idea is to avoid data transfers between the nucleus and satellites, and burst-process all data
on the nucleus to deriver the final products quickly.
The nuclei are defined as **bare** **nuclei** by adding
:green:`bareNucleus=only` or :green:`bareNucleus=allow` in the ``catchall`` field in CRIC.
The former accepts only full-chain workflows while the latter accepts normal workflows in addition to full-chain
workflows. Tasks can set the ``fullChain`` parameter to use the mechanism. The value can be

* :hblue:`only` to be assigned to a nucleus with :green:`bareNucleus=only`,
* :hblue:`require` to be assigned to a nucleus with :green:`bareNucleus=only` or :green:`bareNucleus=allow`, or
* :hblue:`capable`.

When :hblue:`capable` is set, the task is assigned to the same nucleus as that of the parent task only if the parent
task was assigned to a bare nucleus. Otherwise, :hblue:`capable` is ignored and the task can go to a normal nucleus.

Once a task with the ``fullChain`` parameter is assigned to a bare nucleus, the job brokerage sends jobs only
to the queues associated to the nucleus. On the other hand. if a normal task is assigned to a bare nucleus
with :green:`bareNucleus=allow`
or a task with ``fullChain`` = :hblue:`capable` is assigned to a normal nucleus, the job brokerage sends jobs to the
queues associated to satellites in addition to the nucleus.

-----------

|br|

ATLAS Analysis Job Brokerage
-------------------------------------

This is the ATLAS analysis job brokerage flow:

#. First, the brokerage counts the number of running/queued jobs/cores for the user
   (or the working group if the task specifies ``workingGroup``), checks the global disk quota, and check the classification of the task.
   The brokerage throttles the task (not going to submit jobs for the task) if ANY of the following conditions holds:

    **Number of User Jobs Exceeds Caps**

      * the number of running jobs is larger than ``CAP_RUNNING_USER_JOBS``
      * the number of queued jobs is larger than 2  :raw-html:`&times;` ``CAP_RUNNING_USER_JOBS``
      * the number of running cores is larger than ``CAP_RUNNING_USER_CORES``
      * the number of queued cores is larger than 2  :raw-html:`&times;` ``CAP_RUNNING_USER_CORES``

      |br|

      .. line-block::
        For the working group it uses ``CAP_RUNNING_GROUP_JOBS`` and ``CAP_RUNNING_GROUP_CORES`` instead.
        All ``CAP_blah`` are defined in :doc:`gdpconfig </advanced/gdpconfig>`.


    **User's Usage Exceeds Quota**

      * the global disk quota exceeds

      |br|


    **User Analysis Share Usage Exceeds its Target and the Task is in Lower Class**

      .. line-block::
        Currently this part of throttle is only for User Analysis share. Tasks in other shares are immune to it
        (For task and site classification, see :doc:`Site & Task Classification </advanced/site_task_classification>`)

      * the User Analysis task is in class C , and User Analysis share usage > 90% of its target
      * the User Analysis task is in class B , and User Analysis share usage > 95% of its target
      * the User Analysis task is in class A , and User Analysis share usage > max(``USER_USAGE_THRESHOLD_A``/(# of user's running slots in hi-sites), 1)*100% of its target


#. Next, the brokerage generates the list of preliminary candidates as follows:

   * Take all queues with type='analysis' or 'unified'.

   * Exclude queues if ``excludedSite`` is specified and the queues are included in the list.

   * Exclude queues if ``includedSite`` is specified and the queues are not included in the list.
     Pre-assigned queues are specified in ``includedSite`` or ``site``.

#. Then, the brokerage filters out preliminary candidates that don't pass any of the following checks:
   There are two types of filters, filters for persistent issues and filters for temporary issues.

   * Filters for persistent issues
       * The queue status must be *online* unless the queues are pre-assigned.

       * Input data locality check to skip queues if they don't have input data locally. This check is suppressed
         if ``taskPriority`` :raw-html:`&GreaterEqual;` 2000,
         ``ioIntensity`` :raw-html:`&le;` ``IO_INTENSITY_CUTOFF_USER``, or the last successful brokerage cycle
         happened more than ``DATA_CHECK_TIMEOUT_USER`` hours ago, where ``IO_INTENSITY_CUTOFF_USER`` and
         ``DATA_CHECK_TIMEOUT_USER`` are defined in :doc:`gdpconfig </advanced/gdpconfig>`.

       * Check with ``MAX_DISKIO_DEFAULT`` limit defined in :doc:`gdpconfig </advanced/gdpconfig>`.
         It is possible to overwrite the limit for a particular queue through the ``maxDiskIO`` (in kB/sec per core)
         field in CRIC. The limit is applied in job brokerage: when the average diskIO per core for running jobs in
         a queue exceeds the limit, the next cycles of job brokerage will exclude tasks with ``diskIO`` higher than
         the defined limit to progressively get the diskIO under the threshold.

       * CPU Core count matching.

       * Skip VP queues if the task specifies ``avoidVP`` or those queues are overloaded.

       * Availability of ATLAS release/cache. This check is skipped when queues have *ANY* in the ``releases`` filed in CRIC.
         If queues have *AUTO* in the ``releases`` filed, the brokerage uses the information published in a json by CRIC as
         explained at :ref:`this section <ref_auto_check>`.

       * Queues publish maximum (and minimum) memory size per core. The expected memory site of each job is estimated
         for each queue as

         .. math::

            (baseRamCount + ramCount \times coreCount) \times compensation


         if ``ramCountUnit`` is *MBPerCore*, or

         .. math::

            (baseRamCount + ramCount) \times compensation

         if ``ramCountUnit`` is *MB*,
         where *compensation* is 0.9, avoiding sending jobs to high-memory queues when their expected memory usage is
         close to the lower limit. Queues are skipped if the estimated memory usage is not included in the acceptable
         memory ranges.

       * The disk usage for a job is estimated as

         .. math::

            (0 \: or \: inputDiskCount) + outDiskCount \times inputDiskCount + workDiskCount

         *inputDiskCount* is the total size of job input files.
         The first term in the above formula is zero
         if the queues are configured to read input files directly from the local storage. ``maxwdir`` is divided by
         *coreCount* at each queue and the resultant value must be larger than the expected disk usage.

       * DISK size check, free space in the local storage has to be over 200GB.

       * Skip blacklisted storage endpoints.

       * Analysis job walltime is estimated using the same formula as that for production jobs.
         The estimated walltime must be between ``mintime`` and ``maxtime`` at the queue.

       * Skip queues without pilots for the last 3 hours.

   * Filters for temporary issues
       * Skip queues if there are many jobs from the task closed or failed for the last ``TW_DONE_JOB_STAT`` hours.
         (nFailed + nClosed) must be less than max(2 :raw-html:`&times;` nFinished, ``MIN_BAD_JOBS_TO_SKIP_PQ``).
         ``TW_DONE_JOB_STAT`` and ``MIN_BAD_JOBS_TO_SKIP_PQ`` are defined in :doc:`gdpconfig </advanced/gdpconfig>`.

       * Skip queues if defined+activated+assigned+starting > 2 :raw-html:`&times;` max(20, running).

       * Skip queues if the user has too many queued jobs there.

   * Filters to control user queue length on each PQ per ghsare: Analysis Stabilizer
       * First, decide whether the PQ can be throttled.
         The PQ will NOT be throttled if it does not have enough queuing jobs; that is, when any condition of the following is satisfied:

          * nQ(PQ) < ``BASE_QUEUE_LENGTH_PER_PQ``

          * nQ(PQ) < ``BASE_EXPECTED_WAIT_HOUR_ON_PQ`` * trr(PQ)
         where trr stands for to-running-rate = number of jobs getting from queuing to running per hour in the PQ; it is evaluated according to jobs with starttime within last 6 hours

       * If the PQ does not meet any condition above, it can be throttled.
         Then compute nQ_max(PQ) (i.e. the affordable max queue length of each PQ), which is the max among the following values:

          * ``BASE_QUEUE_LENGTH_PER_PQ``

          * ``STATIC_MAX_QUEUE_RUNNING_RATIO`` * nR(PQ)

          * ``MAX_EXPECTED_WAIT_HOUR`` * trr(PQ)

       * Next, compute what percentage of nQ_max(PQ) is for the user:

          * percentage(PQ, user) = max( nR(PQ, user)/nR(PQ) , 1/nUsers(PQ) )

       * Finally, the max value among the following, called *max_q_len* , will be used to throttle nQ(PQ, user)

          * ``BASE_DEFAULT_QUEUE_LENGTH_PER_PQ_USER``

          * ``BASE_QUEUE_RATIO_ON_PQ`` * nR(PQ)

          * nQ_max(PQ) * percentage(PQ, user)

       * Thus, if nQ(PQ, user) > *max_q_len* , the brokerage will temporarily exclude the PQs in which the user of the task already has enough queuing jobs

       * Parameters mentioned above: ``BASE_DEFAULT_QUEUE_LENGTH_PER_PQ_USER``, ``BASE_EXPECTED_WAIT_HOUR_ON_PQ``, ``BASE_QUEUE_LENGTH_PER_PQ``, ``BASE_QUEUE_RATIO_ON_PQ``, ``MAX_EXPECTED_WAIT_HOUR``, ``STATIC_MAX_QUEUE_RUNNING_RATIO`` are defined in :doc:`gdpconfig </advanced/gdpconfig>`

#. Finally, it calculates the brokerage weight for remaining candidates using the following formula.

   **Original basic weight**

   .. math::

     weight = \frac {running + 1} {(activated + assigned + starting + defined + 1)}

   The brokerage uses the largest one as the number of running jobs among the following numbers:

   * The actual number of running jobs at the queue, *R*\ :sub:`real`.

   * min(*nBatchJob*, 20) if *R*\ :sub:`real` < 20 and *nBatchJob* (the number of running+submitted
     batch workers at PQ) > *R*\ :sub:`real`. Mainly for bootstrap.

   * *numSlots* if it is set to a positive number for the queue to the `proactive job assignment <https://github.com/HSF/harvester/wiki/Workflows#proactive-job-assignment>`_.

   * The number of starting jobs if *numSlots* is set to zero, which is typically useful for Harvester to fetch
     jobs when the number of available slots dynamically changes.

   * Currently original basic weight is used in brokerage.


   **New basic weight**

   New basic weight = :math:`W_s \cdot W_q` , where

    * :math:`W_s` : weight from **site-class**
       * For jobs in User Analysis and Express Analysis: :math:`W_s` is shown in the table

            .. list-table::
               :header-rows: 1

               * - Task Class
                 - hi-site
                 - mid-site
                 - lo-site
               * - S or A
                 - :math:`N_j`
                 - :math:`\epsilon_1`
                 - :math:`\epsilon_2`
               * - B
                 - :math:`\epsilon_2`
                 - :math:`N_j`
                 - :math:`\epsilon_1`
               * - C
                 - :math:`\epsilon_2`
                 - :math:`\epsilon_1`
                 - :math:`N_j`

          where

             * :math:`N_j`: estimated number of jobs to submit in the brokerage cycle
             * :math:`\epsilon_1`, :math:`\epsilon_2`: some small positive numbers (not fixed) to avoid dead zero; :math:`\epsilon_1 > \epsilon_2`

          The purpose is to broker time-sensitive tasks to high-appropriateness analysis sites more, and vice versa.

          (For task and site classification, see :doc:`Site & Task Classification </advanced/site_task_classification>`)

       * For other analysis shares (group shares, ART, etc.): :math:`W_s = N_j` . (Task- and site-classification are NOT considered)

    * :math:`W_q`: weight from **queue length**

      .. math::

        W_{q} = \frac { \text{max_q_len}(PQ, user) - \text{nQ}(PQ, user) - N_{j} / N_{PQ} } { ( \sum_{\text{candidate PQs}} ( \text{max_q_len}(PQ, user) - \text{nQ}(PQ, user) ) ) - N_{j} }

      where :math:`N_{PQ}` = number of candidate PQs; :math:`\text{nQ}` and :math:`\text{max_q_len}` are defined in Analysis Stabilizer

      The purpose is to control the queue length in the same way of Analysis Stabilizer.


   New basic weight will soon be deployed to replace the original basic weight

#. If all queues are skipped due to the persistent issues, the brokerage tries to find candidates without the input
   data locality check. If all queues are still skipped, the task is pending for 20 min.
   Otherwise, the remaining candidates are sorted by weight, and the best 10 candidates are taken.

|br|
